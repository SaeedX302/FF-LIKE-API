These tests are written for pytest and target the `token_ind_json` public interface. That interface may be provided as one of the following:

- A function named `token_ind_json` (preferred).
- A function with a semantically similar name (`token_index_to_json`, `serialize_token_indices`, `to_token_index_json`).
- A class `TokenIndJson` exposing a `to_json`, `token_ind_json`, `serialize`, or `convert` method.

They are designed to be resilient to minor refactorings introduced in pull requests while focusing on:

- Happy path behavior.
- Robustness with edge cases (empty input, duplicate tokens, Unicode characters).
- Invalid input handling.
- Determinism and stability of indexing.
- Sanity checks for larger inputs.

If the implementation module path differs, adjust the candidate list inside `tests/test_token_ind_json.py::_import_impl`.