# Fix: Missing or Incorrect Prototype

**Category**: `missing_prototype`
**Trigger**: Function lacks a typed prototype, or return type is unresolved

## Allowed Tools
- `set_function_prototype`
- `get_function_variables` (to refresh after prototype change)
- `rename_variables` (to fix names after type changes)
- `get_function_callers` + `decompile_function` (caller-role skim — see step 1)

## Recipe

1. **Caller-role skim** (do this BEFORE picking parameter names or a function name):
   read 1–2 callers and ask *"what would the caller's author write in a comment
   above this call site?"* The answer is the function's role; parameter names
   and the function name should both reflect that role, not the body's
   mechanism. If callers are unavailable, fall back to placeholder names
   (`<Class>__Func<addr>`, `dwParam1`) rather than inventing body-summary
   names. See core.md "Purpose over Mechanism".
2. **Analyze the decompiled source** to determine:
   - Return type: what does EAX hold at each RET? void, int, pointer, bool?
   - Parameter types: how are stack/register params used?
   - Calling convention: __stdcall, __cdecl, __fastcall, __thiscall
   - **Class membership**: if `__thiscall` or implicit-register `this`, check
     whether the function's address appears in a known vtable (see core.md
     "Known C++ Class Hierarchy"). This determines the correct class prefix
     if the function also needs renaming.
3. **Set prototype**: `set_function_prototype(function_address=..., prototype=...)`
   - The address parameter is named `function_address` (not `address`), and the
     prototype string parameter is named `prototype`.
   - Use typed struct pointers when the struct is known
   - Use Hungarian camelCase for parameter names
4. **Refresh variables**: `get_function_variables(address=...)` -- prototype changes may create new SSA variables; use the function address, not the name, in the same pass
5. **Fix names if needed**: single `rename_variables` call for any new variables
6. Scoring is handled externally -- do not call `analyze_function_completeness`.

## Important
- Prototype changes wipe plate comments. If plate comment exists, note its content before changing prototype and reapply it in the same pass.
- Prototype changes trigger re-decompilation. Variable list will be stale after this step.
- `set_function_prototype` does not rename the function. If the function name also needs to change, call `rename_function_by_address` separately.
