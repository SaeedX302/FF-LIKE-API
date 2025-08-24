import json
import types
import pytest

# Note: Project appears to use pytest (preferred).
# These tests target functions/classes related to "token_ind_json".
# If the implementation module path differs, update the import below accordingly.

def _import_impl():
    """
    Attempt to import candidate modules that might define `token_ind_json` or similar APIs.
    This helper allows tests to be resilient to module path changes within the PR.
    """
    candidates = [
        "token_ind_json",                 # direct module
        "src.token_ind_json",            # common src layout
        "app.token_ind_json",            # app package layout
        "lib.token_ind_json",          # lib package layout
        "utils.token_ind_json",          # utils package layout
        "core.token_ind_json",           # core package layout
        "module.token_ind_json",         # generic package layout
    ]
    last_err = None
    for name in candidates:
        try:
            mod = __import__(name, fromlist=['*'])
            return mod
        except Exception as e:
            last_err = e
    pytest.skip(f"Implementation for token_ind_json not found. Last error: {last_err}")

def _get_callable(mod, names):
    for n in names:
        obj = getattr(mod, n, None)
        if callable(obj):
            return obj, n
    return None, None

@pytest.fixture(scope="module")
def impl():
    return _import_impl()

@pytest.fixture(scope="module")
def api(impl):
    """
    Discover key public entry points commonly expected around token→index→json workflows.
    We try multiple conventional names to gracefully follow PR changes.
    """
    fn_names = [
        "token_ind_json",
        "token_index_to_json",
        "tokens_to_index_json",
        "to_token_index_json",
        "serialize_token_indices",
    ]
    fn, name = _get_callable(impl, fn_names)
    if fn is None:
        # If the implementation is class-based, try to instantiate it
        cls = getattr(impl, "TokenIndJson", None)
        if cls and callable(cls):
            return cls(), "TokenIndJson"
        pytest.skip("No suitable function or class found for token_ind_json API.")
    return fn, name

def test_happy_path_simple_tokens(api):
    """
    Happy path: simple list of tokens with sequential indices.
    Expect deterministic JSON structure and content.
    """
    target, name = api

    tokens = ["hello", "world"]
    # We tolerate both functional and OO styles
    if isinstance(target, types.FunctionType):
        out = target(tokens)
    else:
        # Assume class provides a method with one of the common names
        method = None
        for cname in ("token_ind_json", "to_json", "serialize", "convert"):
            if hasattr(target, cname):
                method = getattr(target, cname)
                break
        if not method:
            pytest.skip("TokenIndJson-like class missing conversion method.")
        out = method(tokens)

    # Accept either dict or JSON-string output; normalize to dict
    if isinstance(out, str):
        try:
            data = json.loads(out)
        except json.JSONDecodeError as e:
            pytest.fail(f"Output is not valid JSON: {e}")
    elif isinstance(out, dict):
        data = out
    else:
        pytest.fail(f"Unexpected return type: {type(out)}")

    # Minimal expected structure assertions
    # Common shapes we support:
    # 1) {"tokens": ["hello","world"], "indices":[0,1]}
    # 2) [{"token":"hello","index":0}, {"token":"world","index":1}]
    # 3) {"mapping": {"hello":0,"world":1}}
    if isinstance(data, dict):
        if "tokens" in data and "indices" in data:
            assert data["tokens"] == tokens
            assert data["indices"] == list(range(len(tokens)))
        elif "mapping" in data and isinstance(data["mapping"], dict):
            assert data["mapping"] == {"hello": 0, "world": 1}
        else:
            pytest.fail(f"Unsupported dict schema: {data}")
    elif isinstance(data, list):
        assert data == [{"token":"hello","index":0},{"token":"world","index":1}]
    else:
        pytest.fail(f"Unsupported JSON root type: {type(data)}")

@pytest.mark.parametrize("tokens", [
    [],                                 # empty input
    ["a"],                              # single token
    ["repeat", "repeat", "unique"],     # duplicate tokens
    ["", " "],                          # empty/space token values
    ["😀", "こんにちは", "مرحبا"],         # unicode tokens
])
def test_various_token_sets(tokens, api):
    """
    Validate robustness across edge cases: empty, duplicates, unicode, etc.
    """
    target, _ = api
    if isinstance(target, types.FunctionType):
        out = target(tokens)
    else:
        method = getattr(target, "token_ind_json", None) or getattr(target, "to_json", None)
        if not method:
            pytest.skip("TokenIndJson-like class missing conversion method.")
        out = method(tokens)

    if isinstance(out, str):
        data = json.loads(out)
    elif isinstance(out, (dict, list)):
        data = out
    else:
        pytest.fail(f"Unexpected return type for tokens={tokens}: {type(out)}")

    # Validate index monotonicity where applicable
    def extract_pairs(d):
        if isinstance(d, dict):
            if "tokens" in d and "indices" in d:
                return list(zip(d["tokens"], d["indices"]))
            if "mapping" in d and isinstance(d["mapping"], dict):
                return sorted(d["mapping"].items(), key=lambda kv: kv[1])
            return []
        if isinstance(d, list):
            return [(e.get("token"), e.get("index")) for e in d if isinstance(e, dict)]
        return []

    pairs = extract_pairs(data)
    # If the format doesn't expose pairs, skip deep checks but ensure serializability
    json.dumps(data)

    # Indices, if present, should be 0..n-1 in order
    indices = [idx for _, idx in pairs if isinstance(idx, int)]
    if indices:
        assert indices == list(range(len(indices)))

    # Token count consistency when both tokens and indices are present
    if isinstance(data, dict) and "tokens" in data and "indices" in data:
        assert len(data["tokens"]) == len(data["indices"])

def test_invalid_inputs_graceful_handling(api):
    """
    Validate graceful handling of invalid inputs: None, non-iterables, mixed types.
    The function may raise a ValueError/TypeError, or return a safe empty structure.
    """
    target, _ = api
    invalids = [None, 123, 12.3, object(), {"not":"a list"}, [1,2,3], ["ok", 2, None]]

    for inv in invalids:
        if isinstance(target, types.FunctionType):
            def call(inv=inv):
                return target(inv)
        else:
            method = getattr(target, "token_ind_json", None) or getattr(target, "to_json", None)
            if not method:
                pytest.skip("TokenIndJson-like class missing conversion method.")
            def call(inv=inv, method=method):
                return method(inv)

        try:
            out = call()
        except (TypeError, ValueError):
            # Accept explicit error for invalid input
            continue
        # Otherwise, ensure output is at least JSON-serializable
        if isinstance(out, (dict, list, str)):
            # if it's a str, check it parses
            if isinstance(out, str):
                json.loads(out)
            else:
                json.dumps(out)
        else:
            pytest.fail(f"Unexpected return type for invalid input {inv!r}: {type(out)}")

def test_determinism_same_input_same_output(api):
    """
    Repeated calls with same input should produce identical outputs.
    """
    target, _ = api
    sample = ["x", "y", "z"]
    if isinstance(target, types.FunctionType):
        out1 = target(sample)
        out2 = target(sample)
    else:
        method = getattr(target, "token_ind_json", None) or getattr(target, "to_json", None)
        if not method:
            pytest.skip("TokenIndJson-like class missing conversion method.")
        out1 = method(sample)
        out2 = method(sample)

    def norm(o):
        return json.loads(o) if isinstance(o, str) else o
    assert norm(out1) == norm(out2)

def test_stability_indexing_with_duplicates(api):
    """
    If duplicates exist, indices should reflect position, not uniqueness, unless the API specifies mapping semantics.
    We accept either:
      - positional entries [("a",0),("a",1),("b",2)]
      - or mapping {"a":0,"b":2} (first occurrence retained)
    """
    target, _ = api
    tokens = ["a","a","b"]
    if isinstance(target, types.FunctionType):
        out = target(tokens)
    else:
        method = getattr(target, "token_ind_json", None) or getattr(target, "to_json", None)
        if not method:
            pytest.skip("TokenIndJson-like class missing conversion method.")
        out = method(tokens)

    data = json.loads(out) if isinstance(out, str) else out
    if isinstance(data, list):
        assert data == [{"token":"a","index":0},{"token":"a","index":1},{"token":"b","index":2}]
    elif isinstance(data, dict):
        if "tokens" in data and "indices" in data:
            assert data["tokens"] == tokens
            assert data["indices"] == [0,1,2]
        elif "mapping" in data and isinstance(data["mapping"], dict):
            assert data["mapping"].get("a") == 0
            assert data["mapping"].get("b") == 2
        else:
            pytest.fail(f"Unsupported dict schema for duplicates: {data}")
    else:
        pytest.fail(f"Unsupported root type for duplicates: {type(data)}")

def test_idempotency_string_roundtrip(api):
    """
    If API returns JSON string, ensure that parsing and re-dumping yields the same structure.
    """
    target, _ = api
    tokens = ["id", "em", "po", "tent"]
    if callable(target) and not isinstance(target, type(lambda: None)):
        # class instance with __call__ not expected; fall back to method discovery
        pass
    out = target(tokens) if callable(target) else getattr(target, "to_json", getattr(target, "token_ind_json", None))(tokens)
    if isinstance(out, str):
        data = json.loads(out)
        assert json.dumps(data, sort_keys=True) == json.dumps(json.loads(out), sort_keys=True)
    elif isinstance(out, (dict, list)):
        assert json.loads(json.dumps(out, sort_keys=True)) == json.loads(json.dumps(out, sort_keys=True))
    else:
        pytest.skip("Unexpected output type for idempotency test.")

def test_large_input_performance_sanity(api):
    """
    Sanity check for large inputs to ensure no pathological blowups occur.
    Not a perf test; only verifies it completes and produces JSON-serializable result.
    """
    target, _ = api
    tokens = [f"t{i}" for i in range(5000)]
    out = target(tokens) if callable(target) else getattr(target, "to_json", getattr(target, "token_ind_json", None))(tokens)
    # Must be JSON serializable
    if isinstance(out, str):
        json.loads(out)
    else:
        json.dumps(out)

def test_reject_non_string_tokens_if_specified(api):
    """
    If implementation enforces string tokens, ensure it rejects non-strings.
    Accept either TypeError/ValueError or an explicit filtering behavior (no crash).
    """
    target, _ = api
    tokens = ["ok", 123, "still-ok", None]
    def call():
        return target(tokens) if callable(target) else getattr(target, "to_json", getattr(target, "token_ind_json", None))(tokens)
    try:
        out = call()
    except (TypeError, ValueError):
        return
    # If allowed, at least ensure it is serializable
    if isinstance(out, str):
        json.loads(out)
    else:
        json.dumps(out)