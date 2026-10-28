# Clothing Mesh Editor 0.5

Run **ClothingMeshEditor.exe** from the portable distribution, or **Release\ClothingMeshEditor.exe** after building from source. The **0.5 Portable** distribution includes its own Python 3.14 runtime, libraries and Visual C++ runtime for Windows x64. Extract the entire ZIP into a writable folder before launching. No Python installation or pip is needed. Keep the `runtime` folder and application files beside the executable.

## Build in Rider

Open `ClothingMeshEditor.sln`, select **Release | x64**, then **Build Solution**. The build machine needs Visual Studio 2022 or newer Build Tools with **Desktop development with C++** and a Windows SDK. No local Python, virtual environment or pip restore is required: the complete runtime is already in `runtime/`.

The same build is available from the command line:

```bat
build.cmd
```

The build compiles both the launcher and `CmaMeshSimplifier.dll`, then copies all runtime libraries, the guide and third-party licenses into `Release/`:

```text
Release/
  ClothingMeshEditor.exe
  CmaMeshSimplifier.dll
  app.py, core.py, viewer.py
  runtime/                 Python, Qt, NumPy, UnityPy, codecs and VC++ runtime
  licenses/meshoptimizer.md
  Clothing_Mesh_Editor_0.5_Modeller_Guide_EN.pdf
  README.md, requirements.txt
```

Distribute the **entire contents of `Release/`**. The receiving Windows x64 computer needs no Python, .NET, Visual Studio or Visual C++ Redistributable installation. Package and Python licenses stay inside `runtime/`; meshoptimizer's native backend license is in `licenses/`. Intermediate compiler files stay in `build/`, outside the portable folder. Rebuild with `build.cmd /t:Rebuild`.

## Workflow

1. Open a clothing `.bundle`, or drag it onto the window. Keep its `catalog*.json` and `.hash` files beside it.
2. Select a mesh if the bundle contains several. The viewer shows one mesh in its local bind pose with its base-color texture when available. It uses simple lighting, not the game's HDRP shader.
3. Set **Triangles to keep** or use the percentage slider. **Allowed error** controls meshoptimizer's weighted geometry/attribute error budget; it is not a guaranteed visual-error percentage.
4. Choose **Preserve boundaries** to lock mesh borders, or **Flexible boundaries** to allow boundary simplification. Both preserve material partitions and, with Aggressive off, UV seams. Both retain original attributes on surviving vertices. Exact duplicate vertices may be welded only when all vertex streams and morph deltas match. Each submesh goes to the simplifier with only the vertices it uses: before 2026-10-25 the copies left over from welding stayed in the buffer, and meshoptimizer locked every vertex that had such a copy at its position as a seam. Daemon High Heels (72,954 triangles, a third of them duplicated faces) stopped at about 55,000 triangles whatever the target; now 50% leaves 36,444. Points shared by two submeshes are locked, so the submeshes keep meeting without cracks.
   **Aggressive simplification (relax seams)** is **OFF by default**. Enable it when the regular simplifier stops far above your target. It uses meshoptimizer v1.0's permissive mode to allow collapses across attribute discontinuities. UVs, shading and the silhouette can change; compare the result before exporting. The error budget, boundary mode and detail protection still apply, so the target remains approximate. For stronger reduction, try detail protection 0-25, then Apply. Unchecking the box and applying again uses the original simplifier on the loaded original mesh.
   Set **Fine detail protection** (0-100; default 0). **0** is off: no vertex is locked by it. Higher values protect more tightly curved areas and geometric creases from edge collapse, so more triangles remain: on Quarter Zip Training Top, 25% target, 50 leaves 61,928 triangles where 0 leaves 50,001; on Daemon High Heels, 50% target, 50 leaves 49,076 where 0 leaves 36,444. Change the slider and click **Apply** to update; the result panel shows the value used for the current result. For small decorations or folds, try 70-90 and compare. If reduction becomes too limited, lower it or accept a higher triangle count.
5. Click **Apply simplification**. Work runs on a background thread. Every Apply starts from the loaded original, not the previous simplified result. The result can exceed the target when seams, topology or the error budget prevent further collapses.
6. Use **Compare: show original**, **Wireframe** and **Reset selected mesh** to inspect changes. Left drag orbits, right/middle drag pans, wheel zooms, double click frames the mesh.
   **Face orientation** colours the front side of every triangle blue and the back side red. Garments drawn one-sided in the game show only the blue side, so an inside-out mesh looks red from outside. The ordinary view lights both sides alike and does not show the difference.
   **Flip normals outward** turns every piece of the selected mesh that faces inward so it faces away from the wearer, as Blender's Recalculate Outside; pieces already facing out stay. A piece is a set of triangles joined through shared points. A turned piece has its triangles' corner order reversed and its normals, morph normals and tangent sign (w) negated; positions, UVs, tangent directions and skinning stay. It turns Face orientation on, works with or without simplification, and is undone by **Reset selected mesh**. The result panel shows how many pieces were turned.
   How a piece is judged: a closed piece by the sign of its volume. An open piece that wraps around space (a skirt, a sleeve, a cuff, a shoe's upper, a lining) by rays from 8 to 16 random points of its faces, both ways along the face normal: the side where the ray meets the piece itself is inside, so a lining ends up facing the shell, not the body. It is turned when three quarters of its rays say inward and three times as many as say outward. A flat piece (a stripe, a patch, a stud) and a curl open to one side (a frog button) stay as they are: their shape does not tell which side is out. Only the shape decides, so a second click turns nothing.
   Checked on 18 garments: Daemon High Heels stores one shoe inside out and gets just that shoe turned (back sides seen from outside drop from 5.4 million to 41,000 pixels over 48 views); Glen Check Coat gets its two inside-out sleeve cuffs turned; Quarter Zip Training Top 41 of its 1,575 small pieces (thin tubes of the zipper and threads); the other 15 (skirts, dresses, both hoodies, lingerie, stockings, the Cheongsam, four more pairs of shoes) get nothing. Rules tried and dropped because they turned visible stripes, studs or ornaments the wrong way: crossing parity, the first hit's distance, the facing of the nearest surface, the number of layers, the facing of the surface below. Every clothing material checked is HDRP Double-Sided, so the game draws both sides anyway; there a turn changes the direction of the normals (lighting, tessellation displacement), not what is visible.
   **Triangles / Quads**, beside the mesh selector, switches the wireframe and turns it on. Quad display hides the diagonal of suitable adjacent triangle pairs within each submesh. Pairing requires a convex, nearly coplanar four-sided outline; boundaries, sharp folds and unmatched triangles remain visible. This is an inferred display, not recovery of the author's original quad topology. It never changes the mesh or export.
7. **Export optimized mod** asks for a parent folder and creates a new folder with the original mod's name. All applied mesh edits (simplification and flipped normals) are exported together. Existing output folders and the source folder cannot be overwritten.

## Export

Export compacts vertex streams, rebuilds triangle indices, remaps blend-shape indices, and preserves skin weights, bone IDs, bind poses, materials, textures and asset IDs. Stale baked collision data is cleared for changed meshes. External vertex streams of modified meshes are brought into the serialized mesh; other resource data stays intact.

Turned pieces are written with reversed triangles, negated normals (float32, float16, SNorm8 or SNorm16 channels), negated tangent w and negated morph normal deltas. The exported bundle is reopened and its counts, positions and UVs (and with turned pieces its normals and triangle order) are checked before the output folder is committed. Matching Addressables catalogs receive the new uncompressed CRC32, bundle size and cache hash, and their `.hash` files are refreshed. Other top-level files beside the source bundle are copied unchanged. Nested folders are not copied.

With the game closed, back up the original mod folder, then replace its contents with the exported files. Keep the original mod folder name: catalog paths depend on it. Exported files are **not automatically installed**.

## Scope and limits

Fine detail protection is based on local curvature relative to the mesh's overall size and the angle between neighbouring faces. It is not a painted selection or semantic recognition of a zipper, seam or ornament. Flat thin shapes, disconnected pieces and texture-only details are not automatically identified as important. It protects the base geometry, not every animated or morphed pose. **100 is the strongest setting, not a guarantee of lossless geometry.** The allowed error, target count and boundary mode still apply. The curvature scores are cached, so moving the slider does not rescan the mesh on every Apply.

- Intended for Unity triangle-mesh bundles, tested with Daemon High Heels and AERO Sports Hoodie (Unity 2022).
- This is mesh decimation, not quad retopology or a full remesher. Aggressive mode relaxes attribute-seam constraints.
- Variable bone-count streams are supported: all influences of every retained vertex are copied exactly and their offset table is rebuilt. Duplicate welding also compares these full weight lists. The simplifier considers all influences through a compact bone-weight metric when needed. No nearest-surface weight transfer is necessary because it retains original vertices.
- Compressed mesh geometry remains unsupported. Non-triangle meshes are skipped with a warning. Meshes without readable type trees cannot be edited.
- Referenced materials/textures must be inside the same serialized asset. External dependencies are not searched or downloaded; missing textures use a plain material.
- Morphs and skin data are retained, but the viewer does not play animation or morphs. Simplification can alter silhouettes, deformation and shading; inspect the result in the game before replacing a backup.
- No normal mapping, HDRP effects or transparent-material reconstruction. The base-color texture is sufficient to inspect the mesh and UVs. Preview textures are capped at 2048 pixels; exported textures remain unchanged.
- Multiple catalog entries and shifted extra-data offsets are handled. Unsupported catalog encodings fail export rather than silently leave a stale checksum.

## Verified on the supplied sample

Version 0.5: on the current Daemon High Heels file (55,375 triangles), target 10,000, 1% error, Preserve boundaries, detail protection 0: regular leaves **34,449**, aggressive leaves **16,374** triangles. Protection 75 with aggressive leaves **19,572**, retaining all protected geometric positions. Switching aggressive off reproduces v0.4's exact index arrays.

Original: **72,954 triangles, 65,683 vertices**. Preserve-boundaries mode, 1% error, detail protection 0 (since 2026-10-25): 50% target leaves **36,444**, 25% leaves **35,168**, 10% leaves **35,133** triangles; aggressive at 25% leaves **17,988**. Below about 35,000 the UV seams stop the regular simplifier (the shoes have 42,109 position/UV pairs on 23,895 positions). Before that date the same 50% gave 55,391 triangles, 30,778 vertices.

`check_export.py <bundle>` verifies unchanged source bytes, triangle/vertex counts, UVs, normals, tangents, skin weights, bone IDs, bind poses, both morphs, texture pixels, unchanged non-mesh objects, catalog CRC/hash and overwrite protection. `check_ui.py <bundle>` exercises Apply, original comparison, wireframe and Reset and captures the editor's own rendered window.

Version 0.2 also passed the full export checks on **AERO Sports Hoodie**: 196,712 → 98,356 triangles and 117,746 → 63,372 vertices at a 50% target and 1% error in preserve-boundaries mode. Its variable-weight data has 1–8 bone influences per vertex. Every retained vertex's full packed weight list is byte-identical after export, and all 29 morph frames, texture pixels and unchanged objects are preserved. The offset table is rebuilt for the new vertex count. Source files were unchanged. Daemon High Heels also passed regression checks.

Version 0.2 avoids keeping a redundant parsed copy of all morphs and avoids deep-copying their entire source tree at export. Large morph-heavy meshes still require significant memory and can take tens of seconds to load/export.

Loading and animation in the actual game have **not** been tested by the editor's automated checks.

## Dependencies and source

- [UnityPy](https://github.com/K0lb3/UnityPy) 1.25.4 — Unity asset reading/writing, MIT.
- [meshoptimizer](https://github.com/zeux/meshoptimizer) through the `meshoptimizer` 0.2.30a0 Python package — mesh simplification, MIT.
- Aggressive mode uses the official meshoptimizer **v1.0** `simplifier.cpp`, `allocator.cpp` and `meshoptimizer.h`, bundled with their MIT license under `native/meshoptimizer`. `native/CmaMeshSimplifier.vcxproj` builds `CmaMeshSimplifier.dll` with the static Visual C++ runtime. The default mode continues to use the existing Python package backend.
- [PySide6 / Qt](https://doc.qt.io/qtforpython-6/) Essentials 6.12.0 — UI and OpenGL widget, LGPLv3/GPLv3/commercial options; used as unmodified dynamically loaded libraries.
- NumPy 2.5.4, Pillow and UnityPy's codec dependencies. Their license/notice files remain in `runtime/Lib/site-packages` (or `.venv/Lib/site-packages` in the development folder).

`requirements.txt` records the bundled direct dependency versions. `build.cmd` finds the installed Visual Studio C++ build tools automatically and builds the solution. Both native binaries use the static Visual C++ runtime; Python and Qt carry their required runtime DLLs. The runtime's `python314._pth` isolates it from installed Python, user packages and environment search paths. No game plugins or game settings are changed.

## Repository

The git copy (`git_ClothingMeshEditor`) carries all runtime libraries. Build it once to create the portable application:

- `app.py`, `core.py`, `viewer.py`: the editor. `check_*.py`: offline checks (`check_flip.py <bundle> <new folder>` turns every other piece, exports, reopens and compares every vertex stream, morph and triangle, then checks that a second Flip normals outward on its export turns nothing). `make_guide.py` writes the PDF guide in `output/pdf` (needs ReportLab and pypdf).
- `runtime/`: Python 3.14 with every dependency from `requirements.txt` in `runtime/Lib/site-packages` and the Visual C++ runtime DLLs. The build copies this directory into `Release/runtime/` without caches.
- `ClothingMeshEditor.sln`, `ClothingMeshEditor.vcxproj`, `native/CmaMeshSimplifier.vcxproj`: the Rider solution and native build projects. `launcher.cpp`: the launcher; `native/meshoptimizer`: the aggressive backend sources and MIT license.
- Run offline checks against the built application with `Release\runtime\python.exe -B check_export.py <bundle>` (or another `check_*.py` script). Its isolated Python imports the application from `Release/`.
- Generated output (`Release`, `build`), IDE settings, `.venv`, caches, game mod bundles and exports (`export`, `Exports`, `TestExport`, `Checks`) are excluded. See `.gitignore`. `.gitattributes` keeps every file under `runtime/` byte for byte.
