# Context

You are reverse engineering the Warhammer Online: Return of Reckoning game client.

# Function Documentation Core Rules

Apply all changes directly in Ghidra via MCP tools. Do not create or edit filesystem files.

## Tool Contract

The available tools have been pre-verified and are listed at the end of this prompt. Only use tools from that list.

If a tool you need is not in the list, STOP and report BLOCKED. Do not substitute unrelated tools to make progress.

## Prohibited Actions

- Do NOT use `run_script_inline`, `run_ghidra_script`, or `run_script` -- no Ghidra scripts
- Do NOT use `curl`, Bash HTTP calls, or direct endpoint access -- use only MCP tools
- Do NOT re-fetch the TARGET function's decompilation (provided inline). You MAY call `decompile_function` on callers or callees for verification.
- Do NOT call `force_decompile` -- use `decompile_function` only for caller/callee verification
- Do NOT retry a failed tool call with the same parameters -- diagnose and adapt
- Do NOT substitute unrelated tools for missing required tools
- You MAY inspect current symbols/comments/struct layout when directly required to apply a listed fix (e.g., `get_struct_layout` before `modify_struct_field`, `search_data_types` before `create_struct`), but do NOT make broad exploratory calls (`list_classes`, `search_functions`)

## Call Budget

If you have made 10+ MCP calls on a single issue without resolution, STOP and report:
```
BLOCKED: FunctionName @ 0xAddress
Issue: [what you're trying to fix]
Obstacle: [what's preventing resolution]
Calls made: N
```

## Verification Policy

Do NOT call `analyze_function_completeness` -- scoring is handled externally after this prompt completes. Focus on applying changes in Steps 1-4, then report DONE.

## Hungarian Notation Reference

```
b:byte  c:char  f:bool  n:int/short  dw:uint/DWORD  w:ushort  l:long
fl:float  d:double  ll:longlong  qw:ulonglong  ld:float10  h:HANDLE
p:void*/ptr  pb:byte*  pw:ushort*  pdw:uint*  pn:int*  pp:void**
sz:char*(local)  lpsz:char*(param)  wsz:wchar_t*  lpcsz:const char*(param)
ab:byte[N]  aw:ushort[N]  ad:uint[N]  an:int[N]
g_:global prefix (g_dwCount, g_pMain, g_szPath)  pfn:func_ptr (PascalCase, no g_)
Struct pointers: p+StructName (pUnit, pInventory, ppItem for double ptr)
```

**Type normalization**: undefined1->byte, undefined2->ushort, undefined4->uint/int/float/ptr (by usage), undefined8->double/longlong. Use Ghidra builtins (dword, byte, ushort) not Windows types (DWORD, BYTE) for `set_local_variable_type`.

## Known C++ Class Hierarchy (vtable-verified)

WAR.exe uses MSVC RTTI. Class membership is confirmed by vtable writes
in constructors and `.?AV<ClassName>@@` RTTI strings. When naming a
function, use these class prefixes ONLY — do not invent class names.

### Entity state descriptors (the `this` for most entity methods)

| Class | Ctor body | Vtable addr | TypeId | Inherits | Key field ranges |
|---|---|---|---|---|---|
| `GameObject` | 0x00431a31 | 0x00A76FD4 | — | (base) | +0x00..+0xDC |
| `MonsterObject` | 0x00432257 | 0x00A7703C | 3 | GameObject | +0xFC equipment, +0x17C armor, +0x268 mesh refs |
| `PlayerObject` | 0x00432ad8 | (inherits) | 2 | MonsterObject | extends Monster fields |
| `StaticObject` | 0x00432f5a | — | 1 | GameObject | minimal |
| `VfxObject` | 0x00432da5 | — | 4 | GameObject | VFX entity |

### Game singletons (g_p* globals — use as `Class__Method` prefix)

| Class | Singleton global | Address | Fns | Notes |
|---|---|---|---|---|
| `Player` | `g_pPlayer` | 0x00F7611C | 91 | Local player; `TargetMgr` at +0x240 |
| `MythicInterface` | `g_pMythicInterface` | 0x00F76110 | 28 | +0xc lua_state, +0xc4/0xc8 screen dims |
| `TextLogMgr` | `g_pTextLogMgr` | 0x00F76130 | 2 | `PostMessage` dispatcher (48 xrefs) |
| `VfxManager` | `g_pVfxManager` | 0x00F782E4 | 9 | Audio/VFX CSV pipeline + slot storage |
| `EffectMgr` | (via VfxManager) | — | 4 | `EmitOrEnqueue` central VFX emitter |
| `DataCollection` | `g_pDataCollectionEntries` | 0x00D66E64 | 19 | StringTable/CSV registry |
| `InfluenceMgr` | `g_pInfluenceMgr` | 0x00F78248 | 8 | Influence chapter records |
| `WarUiModule` | `g_pWarUiModuleManager` | 0x00F76114 | 28 | UI module registry |

### Gamebryo core (Ni* — use NiRTTI name as prefix)

| Class | NiRTTI name addr | Fns | Notes |
|---|---|---|---|
| `NiRefObject` | — | 216 | Ref-counted base (IncRef/DecRef) |
| `NiObject` | 0x00ABBD78 | 44 | Root of Gamebryo hierarchy |
| `NiObjectNET` | 0x00ABBF3C | 26 | Named objects + properties |
| `NiAVObject` | 0x00ABC014 | 30 | Scene-graph transforms |
| `NiNode` | 0x00ABBF50 | 41 | Parent scene-graph node |
| `NiStream` | 0x00ABE2C8 | 56 | Binary serialization |
| `NiDX9Renderer` | 0x00ABE178 | 33 | Direct3D 9 renderer |
| `NiProperty` | 0x00ABBD88 | 8 | Material/alpha/texture props |

### Other frequently-encountered prefixes

| Prefix | Fns | What | RTTI? |
|---|---|---|---|
| `UILib__` | 195 | Lua-bound UI addon API | func reg |
| `GameLib__` | 151 | Lua-bound game API | func reg |
| `Collision__` | 174 | Spatial collision system | partial |
| `EMotionFX__` | 141 | Animation (3rd-party) | yes (80 RTTI) |
| `Entity__` | 132 | Entity registry free fns | module prefix |
| `Network__` | 117 | Network subsystem | module prefix |
| `Protobuf__` | 121 | Google protobuf runtime | yes (RTTI) |
| `ItemLib__` | 94 | Lua-bound item API | func reg |
| `MythUi__` | 45 | Mythic UI framework | yes (RTTI) |
| `Window__` | 68 | Window management | yes (RTTI) |
| `BitSet__` | 26 | Bit-set utility | module prefix |
| `RBTree__` | 50 | MSVC std::map tree ops | template inst. |

### Gamebryo NiRTTI (for Ni* classes)

Gamebryo has its OWN type system separate from MSVC RTTI. Each
`NiObject` subclass has a static `NiRTTI ms_RTTI` (8 bytes):

```c
struct NiRTTI {
    const char* pcName;       // +0x00 — plain ASCII, e.g. "NiNode"
    const NiRTTI* pkBaseRTTI; // +0x04 — parent class (NULL = root)
};
```

These NiRTTI instances live in `.data` (0x00B6Fxxx range) with their
name strings in `.rdata` (0x00ABBxxx–0x00ABExxx). Example chain:
`NiNode` → `NiAVObject` → `NiObjectNET` → `NiObject` → NULL.

Each Ni* class also has a virtual `GetRTTI()` at vtable slot 0 that
returns its static `ms_RTTI`. So for Gamebryo classes:
- The plain ASCII name (e.g. `"NiNode"`) is the authoritative class name
- Both MSVC RTTI (`.?AVNiNode@@`) AND NiRTTI (`"NiNode"`) exist
- Use the NiRTTI name as the class prefix: `NiNode__`, `NiStream__`

To find a Gamebryo class's NiRTTI: search strings for the bare class
name (e.g. `"NiNode"`), then check xrefs — one will be a DATA ref
from the NiRTTI struct in the 0x00B6F range. The parent chain is
walkable from there.

### How to verify class membership

1. **Vtable match**: read 4 bytes at the known vtable address + slot*4;
   if the function's entry point matches → confirmed class method.
2. **Field offset check**: if function reads/writes offsets > +0xDC
   (e.g. +0xFC, +0x17C, +0x268) → MonsterObject (or subclass).
   Fields within +0x00..+0xDC only → could be GameObject base.
3. **RTTI string**: search for `.?AV<ClassName>@@` (MSVC) or the bare
   class name string (Gamebryo NiRTTI) near the vtable address. If no
   RTTI exists for a proposed class name → do not use it.
4. **Constructor write**: search for `MOV dword ptr [reg], <vtable_addr>`
   in the ctor body to confirm vtable ownership.
5. **NiRTTI GetRTTI()**: for Gamebryo classes, vtable slot 0 is
   `GetRTTI()` which returns a pointer to the static `NiRTTI`. Read
   the name pointer at `*(result + 0)` to get the class name string.

### Anti-pattern: fabricated class names

Do NOT create class prefixes that don't correspond to real C++ classes.
Examples of past mistakes:
- `EquipmentVisual__` — no RTTI, no ctor, no vtable. Functions were
  actually `MonsterObject__` methods or `Entity__` free functions.
- `D2Common__` — Diablo 2 artifact from the documentation tool's
  example text, not a WAR.exe class.

When no real class owns a function, use a module/subsystem prefix
(`Entity__`, `Network__`, `Player__`) or the function's address-range
neighbors to infer the subsystem.

## Critical Rules

1. **Ordering**: Complete ALL naming, prototype, and type changes BEFORE plate comment and inline comments. `set_function_prototype` wipes existing plate comments.
2. **Batching**: Use `rename_variables` (single dict), `batch_set_comments` (plate + PRE + EOL in one call). Never loop individual rename/comment calls.
3. **batch_set_comments plate behavior**: Omitting `plate_comment` leaves the existing plate untouched. Passing an empty string explicitly clears it. You can safely call `batch_set_comments` with only inline comments without affecting the plate.
4. **Phantoms**: `extraout_*`, `in_*` variables with `undefined` types are decompiler artifacts. Note in plate comment Special Cases -- do not retry type-setting.
5. **Type-first**: NEVER rename a variable with a Hungarian prefix that doesn't match the variable's current type. This applies to ALL type mismatches, not just `undefined*`. For example: do NOT rename `in_EAX` to `pNode` if its type is `int` -- that creates a `p` prefix on a non-pointer type and the score will drop. Resolve the type first, then rename.
6. **Prefix-type consistency**: After setting a prototype, verify parameter types match Hungarian prefixes. A parameter named `pGame` typed as `int` is a violation -- fix the type to a pointer.
7. **Struct-name collisions**: If a candidate struct name already exists with an incompatible layout, do NOT modify the existing struct. Create a function-specific struct instead (e.g., append `Data`, `Layout`, or the function's domain: `RoomTileAccessData`).

## Naming Confidence Rules

**Prefer underclaiming over guessing.** A correct neutral name is always better than a confident wrong name.

Every renamed variable, struct field, or function must be justified by one of:
- **Direct read/write behavior** in the decompiled code
- **Control-flow role** (loop counter, branch condition, return value)
- **Comparison against known constants** (type IDs, flags, sentinel values)
- **Linked known type evidence** (passed to a typed API, returned from a known function)

If none apply, use a conservative placeholder:
- Variables: `dwUnknown1D0`, `pUnk20`, `nValue04`
- Struct fields: `dwField04`, `pField20`, `nField1D0`
- Structs: `FunctionNameCtx`, `FunctionNameNode` (not generic names like `TileData` unless the role is proven)

**Mark speculation in plate comments**: If a name is inferred but not proven, note it:
```
Special Cases:
  - dwField1D0: Tentative: may be tile limit (compared against 8, gates shuffle path)
  - pField20: Hypothesis: node list pointer based on linked-list traversal pattern
```

**Do NOT**:
- Name a field `dwTileLimit` when it's only checked once against `8` -- use `dwField1D0` with a comment
- Name two adjacent DWORDs `dwRngAddend`/`dwRngMultiplier` when the code writes a 64-bit result across both -- use `dwRngStateLo`/`dwRngStateHi` or leave unnamed
- Comment stack frame sizes, repeated compiler arithmetic, or RNG constants unless they explain behavior
- Comment the same constant family at every occurrence -- document it once at first use unless later uses differ in meaning

## Output Format

```
DONE: FunctionName
Changes: [brief summary of what was changed]
Proven: [changes backed by callers, constants, or typed APIs]
Inferred: [names/types based on internal usage only -- not verified at call sites]
Unresolved: [structural limitations, unfixable items]
```
