# Step 1: Classify Function

## Allowed Tools
- `analyze_for_documentation` (only if not provided inline)
- `rename_function_by_address` (if boundaries need recreating)
- `create_function` (if function needs to be defined)

## Instructions

From the inline `analyze_for_documentation` output:

1. **Verify function boundaries** -- recreate with correct range if incorrect
2. **Check `return_type_resolved`** -- if false, verify EAX at each RET instruction. Check `wrapper_hint`.
3. **Validate existing name** -- even custom names may be wrong. Verify the
   name reflects the function's **role to callers**, not just its instruction
   body. A function whose role is "reset the bundle" is named `Reset` even
   if the body copies then clears. Chained-verb names (`CopyToClearData…`,
   `InitAndPrepare…`) are a smell — flag them for replacement in Step 2.
   See core.md "Purpose over Mechanism".
4. **Check vtable membership** -- if the function is `__thiscall` or has an implicit `this` (ECX/EAX/EDI), check whether its address appears in a known vtable. This determines the class prefix for Step 2. Also check for fabricated class names: if the current name uses a `Class__` prefix, verify that class exists in C++ (RTTI `.?AV` strings, constructor writes vtable). If the class name was invented by a previous session, flag it for correction in Step 2.
5. **Classify for routing**:
   - **Thunks/wrappers** (single call, no logic): fast path -- skip to Step 2 (rename only) then Step 4 (minimal plate comment) then Step 5 (verify). Skip Steps 3.
   - **Vtable methods**: full workflow, but Step 2 must use the correct class prefix from the vtable owner.
   - **Everything else**: full workflow Steps 2-5.
