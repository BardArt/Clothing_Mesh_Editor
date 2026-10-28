from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from pypdf import PdfReader

root = Path(__file__).resolve().parent
output = root / 'output/pdf/Clothing_Mesh_Editor_0.5_Modeller_Guide_EN.pdf'
output.parent.mkdir(parents=True, exist_ok=True)
styles = {
    'title': ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=25, leading=29, textColor=colors.HexColor('#183f32'), spaceAfter=14),
    'h1': ParagraphStyle('Chapter', fontName='Helvetica-Bold', fontSize=21, leading=25, textColor=colors.HexColor('#183f32'), spaceAfter=16),
    'h2': ParagraphStyle('Section', fontName='Helvetica-Bold', fontSize=12, leading=16, spaceBefore=10, spaceAfter=5, keepWithNext=True),
    'body': ParagraphStyle('Body', fontName='Helvetica', fontSize=10.5, leading=15, spaceAfter=8, alignment=TA_LEFT),
    'small': ParagraphStyle('Small', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#46594f'), spaceAfter=10),
}
story = []

def add(text, style='body'):
    story.append(Paragraph(text, styles[style]))

def page(title):
    if story:
        story.append(PageBreak())
    add(title, 'h1')

add('Clothing Mesh Editor<br/>A modeller\'s guide', 'title')
add('Version 0.5 Portable | Windows x64 | Text-only tutorial', 'small')
add('1. Start here', 'h2')
add('Use this tool to reduce the triangle count of clothing stored in a Unity <b>.bundle</b> file. You can inspect the model, try different reductions and export an edited mod folder. You do not need to install Python or set up libraries when using the Portable version.')
add('The basic workflow is: <b>back up the mod, open its bundle, simplify a mesh, compare the result, export, then test in the game.</b>')
add('What the tool does - and does not do', 'h2')
add('The tool removes detail from an existing triangle mesh. It keeps the original data on surviving vertices, including UVs and bone weights, and updates morph indices. It is not a modelling package: it does not let you sculpt, paint weights, rebuild clean quad topology or preview animation. Lower counts do not automatically mean a better model or a guaranteed frame-rate improvement.')
add('Unpack and launch', 'h2')
add('<b>1.</b> Extract the <b>entire Portable ZIP</b> into a folder you can write to. Do not launch the program from inside the ZIP.')
add('<b>2.</b> Keep <b>ClothingMeshEditor.exe</b>, the <b>runtime</b> folder and the other supplied files together. Sending only the EXE will not work.')
add('<b>3.</b> Run <b>ClothingMeshEditor.exe</b>. This guide describes the window titled <b>Clothing Mesh Editor 0.5</b>.')
add('Prepare the clothing files', 'h2')
add('Keep the clothing bundle and its matching <b>catalog*.json</b> and <b>catalog*.hash</b> files together. The catalog tells the game where the assets are and how to load them. A lone bundle is enough for viewing in many cases, but this editor requires a matching catalog beside it to export the mod.')
add('Back up the whole original mod folder <b>outside the game\'s scanned Mods folder</b>. Keep the working folder\'s original name. Do not put a backup copy beside the active mod where the game might load both.')
add('Find your next step', 'h2')
add('Page 2: open and inspect. Page 3: choose settings. Page 4: protect small details. Page 5: aggressive reduction. Page 6: apply and review. Page 7: export. Page 8: install and test. Page 9: common problems.', 'small')

page('2. Open and inspect the model')
add('Load the bundle', 'h2')
add('Click <b>Open .bundle</b> and select the clothing file, or drag the file onto the window. Wait for loading to finish. Large clothing meshes with many morphs can take tens of seconds and use significant memory.')
add('Use the <b>MESH</b> selector on the right to choose the mesh you want to inspect. A bundle can contain more than one mesh. The viewer shows one selected mesh in its local rest pose, not the complete dressed character.')
add('Move around the model', 'h2')
add('<b>Left mouse drag:</b> rotate the view.<br/><b>Right or middle mouse drag:</b> move the view sideways or vertically.<br/><b>Mouse wheel:</b> zoom in or out.<br/><b>Double-click</b> the view or click <b>Frame mesh</b> to return to a useful framing.')
add('Understand the green numbers', 'h2')
add('<b>TRIANGLES</b> is the number of triangles in the displayed mesh. This is the main number you are reducing. <b>VERTICES</b> is the number of points used by the mesh. One visible point can be represented by several vertices at a UV seam or a shading split, so these two counts do not fall at the same rate.')
add('<b>SUBMESHES</b> are sections of the mesh, usually used for different materials. <b>TEXTURED MATERIALS</b> counts material slots with a base-color texture available to the viewer. <b>MORPHS</b> counts shape channels, also called blend shapes.')
add('<b>PREVIEW</b> means the current result is shown. <b>ORIGINAL</b> means you enabled original comparison. The green counts follow that view; the right-hand result text lists both original and applied triangle counts.')
add('Texture and wireframe views', 'h2')
add('<b>Show texture</b> displays the base-color texture when the editor can find it. Lighting is deliberately simple. Normal maps, game-specific shaders and transparency are not reproduced, so the model can look different from the game.')
add('<b>Wireframe</b> shows the edges. Beside the mesh selector, <b>Triangles / Quads</b> switches the wireframe style and turns wireframe on. <b>Quads</b> hides the diagonal between suitable neighbouring triangles. Unpaired triangles and sharp boundaries remain visible.')
add('<b>Quads is only a viewing aid.</b> It does not recover the modeller\'s original quads or turn the export into a quad mesh. The exported geometry remains triangles.')

page('3. Choose simplification settings')
add('Start with a modest reduction', 'h2')
add('For a first attempt, keep about <b>75%</b> of the original triangles and leave <b>Allowed error</b> at <b>1.00%</b>. This is a cautious starting point, not a promise of quality. The editor initially suggests keeping about 50%; move the slider if you want a gentler first test.')
add('For example, on a 100,000-triangle mesh, keeping 75% means asking for about 75,000 triangles. If the result looks good, try 60%, then 50%. Fine lace, jewellery, straps, seams and folds may need more geometry than broad, smooth fabric.')
add('Triangles to keep', 'h2')
add('Type the desired number into <b>Triangles to keep</b>, or use the percentage slider. The percentage means <b>how much to keep</b>, not how much to remove. Keep 30% means remove roughly 70%. These controls apply to the selected mesh, not every mesh in the bundle.')
add('The number is a target. The actual result can be slightly below it or remain well above it. The tool may stop early to respect seams, boundaries, topology or the error budget. Read the applied count after each operation.')
add('Preserve boundaries', 'h2')
add('Use this mode first. It locks open mesh borders during simplification. This is useful around neck openings, sleeves, hems and other places where a changing edge could reveal a gap. Material sections are preserved. UV seams are respected while Aggressive simplification is off.')
add('Flexible boundaries', 'h2')
add('This mode allows more movement of the mesh boundary through triangle removal. Try it if the first mode cannot reduce the mesh enough. Inspect openings and the silhouette carefully. It preserves material sections and, with Aggressive simplification off, UV seams. It does not freely rebuild the entire surface.')
add('Allowed error (% of mesh size)', 'h2')
add('This controls how much change the simplifier is allowed to accept in its combined geometry and attribute calculation. A higher value gives it more freedom; a lower value is more restrictive.')
add('The percentage is <b>not a literal guarantee</b> that every point moves less than that fraction of the garment size. It is also not a visual-quality score. If the target is not reached, try a small increase, such as 1% to 2%, and compare again. Raising it much higher may add no useful reduction.')
add('Change one setting at a time so you can tell which change affected the model. For a better-looking result, keep more triangles or lower the allowed error.')

page('4. Protect small details')
add('Fine detail protection: 0-100', 'h2')
add('This slider asks the tool to keep more geometry around tight curves and sharp creases. It can help preserve rounded decorations, raised seams and small curved features while allowing broader surfaces to simplify. The default is <b>0</b>.')
add('<b>0:</b> off; the tool reduces exactly as before the slider existed. The regular simplifier still respects its seam, topology, boundary and error limits.<br/><b>50:</b> a starting point for mixed fabric and small curved details; it can keep many more triangles.<br/><b>75-100:</b> stronger protection; expect to keep more triangles. Even 100 is not a guarantee that every detail will survive.')
add('How the tool chooses what to protect', 'h2')
add('It looks at changes in the angle of neighbouring faces and how tightly the surface bends compared with the size of the whole mesh. Tight bends and creases receive more protection than broad, nearly flat surfaces. This is an automatic geometry test, not recognition of a zip, button or ornament.')
add('It does not automatically identify flat thin straps, loose pieces or details painted into a texture as important. It also does not test every animated pose or body morph. Always inspect those areas yourself.')
add('Try it step by step', 'h2')
add('<b>1.</b> Choose a triangle target, boundary mode and allowed error. Start with protection 0.<br/><b>2.</b> Click <b>Apply simplification</b>.<br/><b>3.</b> Compare the small details with the original from the same camera angle.<br/><b>4.</b> If a curve or crease loses too much shape, try 50, then 75, and Apply again.<br/><b>5.</b> If too many triangles remain, lower it again and Apply.')
add('The result panel shows <b>Detail protection applied</b>: the value used for the visible result. Moving the slider changes the next operation only. It does not update the mesh until you click Apply.')
add('Why zero may still leave many triangles', 'h2')
add('Zero disables only this extra protection. UV seams, split shading, open borders, topology and the error budget can still stop the regular algorithm. Lowering the target repeatedly cannot remove those limits. If you want to relax attribute-seam restrictions, use the separate Aggressive checkbox described next.')
add('Every trial starts from the loaded original. You can raise protection, lower it again and reapply without accumulating simplification damage within the session.')

page('5. Use aggressive reduction when needed')
add('An optional checkbox, off by default', 'h2')
add('<b>Aggressive simplification (relax seams)</b> allows the tool to simplify across some divisions between vertex attributes, such as UV or shading splits. This can reduce a mesh that the regular algorithm barely changes. It does not automatically turn on when protection is zero.')
add('With the box <b>off</b>, the tool uses the previous regular algorithm. With it <b>on</b>, it uses the permissive mode in meshoptimizer. Both keep the original attributes on surviving vertices, including bone weights. Aggressive mode can change how triangles connect those vertices, so the texture mapping, shading and silhouette can change too.')
add('A practical trial', 'h2')
add('<b>1.</b> First try the regular mode and note the applied count.<br/><b>2.</b> Check <b>Aggressive simplification</b> and keep the other settings unchanged.<br/><b>3.</b> Click <b>Apply simplification</b> and compare counts and appearance.<br/><b>4.</b> If stronger reduction is still needed, try detail protection 25 or 0, then Apply.<br/><b>5.</b> Check texture seams, small parts, openings and the silhouette before exporting.')
add('The result panel says <b>Aggressive applied: On/Off</b>. This describes the current result, while the checkbox controls the next Apply. To return to regular simplification, uncheck it and click Apply again. To remove the reduction entirely, use <b>Reset selected mesh</b>.')
add('Limits that still apply', 'h2')
add('Fine detail protection, the allowed error and the selected boundary mode still matter. Material sections remain separate. The target is still approximate; aggressive mode does not force an exact triangle count and is not a full remesher or a quad generator.')
add('Example: Daemon High Heels', 'h2')
add('On a tested 55,375-triangle shoe mesh, target <b>10,000</b>, allowed error <b>1%</b>, Preserve boundaries and protection <b>0</b>: regular mode kept <b>34,449</b> triangles; aggressive mode kept <b>16,374</b>. Raising protection to <b>75</b> with aggressive mode kept <b>19,572</b>. These are results for that particular source file, not expected counts for every version of the mod.')
add('Export checks passed on the shoes and hoodie, including the retained bone weights and morph data. That checks file integrity; it does not replace testing the garment on the character in motion.')

page('6. Apply, compare and decide')
add('Apply a trial reduction', 'h2')
add('<b>1.</b> Select the mesh and set a target, boundary mode, error budget, detail protection and the Aggressive checkbox.<br/><b>2.</b> Click <b>Apply simplification</b> and wait for completion.<br/><b>3.</b> Read the actual triangle and vertex counts in the result text.<br/><b>4.</b> Inspect the preview before exporting.')
add('Moving a slider alone does not change the mesh. <b>Apply</b> updates the working preview; it does not save a file or install anything into the game.')
add('Every Apply starts from the original mesh loaded in this session. Trying 75%, then 50%, does not simplify the 75% result again. If you open an already optimized bundle, however, that optimized file becomes the new session\'s original.')
add('Use comparison effectively', 'h2')
add('Toggle <b>Compare: show original</b> on and off without moving the camera. Compare at the distance the garment will normally be seen, then zoom in on delicate areas. Switch between textured and wireframe views as needed.')
add('Check the <b>silhouette</b> first: shoulders, sleeve tips, hems, heels and rounded edges. Look for flattened curves, missing thin pieces, new gaps, uneven shading and stretched-looking texture features. Inspect both sides and the inside of openings.')
add('Then check structural details such as zips, cuffs, straps, raised seams and decorations. A technically valid mesh can still lose the detail that makes the design look right.')
add('What Reset and comparison actually change', 'h2')
add('<b>Reset selected mesh</b> restores only that mesh to its loaded original, flip included. Other meshes you have edited keep their changes. Comparison only changes the view: exporting while the original is displayed still exports the applied edits.')
add('With several meshes, select and process them individually. Switching meshes keeps applied edits in memory, but the target control is reset for the newly selected mesh. Check the right-hand <b>Applied</b> count rather than treating the selector\'s original count as the current result.')
add('A real example', 'h2')
add('AERO Sports Hoodie was tested at a 50% target, 1% allowed error and Preserve boundaries. It went from <b>196,712 to 98,356 triangles</b> and from <b>117,746 to 63,372 vertices</b>. Export checks preserved all 29 morphs and the full bone-weight lists of retained vertices. This is one model\'s result, not a universal setting.')
add('The editor does not animate the garment. A good preview is the first check; body fitting, morphs and movement still need a game test.')

page('7. Export the optimized mod')
add('Save all applied edits', 'h2')
add('<b>1.</b> Click <b>Export optimized mod...</b> after applying a change.<br/><b>2.</b> Choose an output <b>parent folder</b> outside the original mod folder.<br/><b>3.</b> Let the editor create a new folder using the source mod folder\'s name.<br/><b>4.</b> Wait for the export-complete message.')
add('For example, if the source folder is <b>AERO Sports Hoodie</b> and you choose <b>Exports/Test_01</b>, the result is placed in <b>Exports/Test_01/AERO Sports Hoodie</b>. Create the Test_01 folder first if you want to use that layout.')
add('Do not select the original mod folder or a folder inside it. Do not select an existing output mod folder as the parent: that can create an unwanted extra nesting level. Choose the directory that should contain the new mod folder.')
add('The editor does not overwrite an existing destination folder. For another attempt, choose a different parent, such as <b>Test_02</b>. This also makes it easy to keep and compare several versions.')
add('What is included', 'h2')
add('The export contains the edited <b>.bundle</b>, matching updated <b>catalog JSON</b> files and their <b>.hash</b> files. The editor updates the bundle information used by the catalog. Treat these files as one set; do not mix an edited bundle with an older catalog.')
add('All applied mesh changes in the current bundle are exported together, including edits to meshes that are not currently selected. Textures and materials are retained. Other files directly beside the source bundle are copied unchanged; nested subfolders are not copied automatically.')
add('If a mod contains several bundles, this operation edits only the bundle you opened. Do not assume the other bundles were simplified. Check any additional files or subfolders before using the exported folder as a complete replacement.')
add('What export verification means', 'h2')
add('The editor reopens the written bundle and checks key mesh data. It also verifies full variable bone-weight lists when present. This catches file-writing problems, but it does not prove that the garment will deform correctly in every pose or that the game will accept every possible mod.')
add('After a successful export, keep the exported folder and your original backup. The program has no saved editing-session format: closing it can discard work that was never exported. A close warning may still appear after exporting; your exported files remain on disk.')

page('8. Install, test and share')
add('Install the exported files', 'h2')
add('<b>1. Close the game.</b> Do not replace clothing files while it is running.')
add('<b>2. Keep the original backup outside the active Mods directory.</b> If you have not made one yet, copy the entire original mod folder there now.')
add('<b>3. Replace the matching files in the original mod folder with the exported set.</b> Keep the original folder name and its location. Copy the updated bundle, catalog JSON and hash together. Preserve any required additional subfolders that the editor did not export.')
add('<b>4. Avoid duplicate active copies.</b> Do not leave both original and optimized copies in locations that the game scans. The export is not automatically installed; choosing an export folder alone does not change the game.')
add('<b>5. Start the game and equip the clothing.</b> First confirm that the correct item loads and has the expected materials.')
add('Test like a modeller', 'h2')
add('Check the garment on the intended body shape. Try the available body sliders or morphs that affect it. For tops, inspect shoulders, armpits, elbows, chest and waist. For shoes, inspect the ankle and the fit around the foot.')
add('Use several poses or animations, especially deep bends and stretches. Look for skin poking through, folds collapsing, visible holes, detached parts or areas that pull toward the wrong bone. Look at hems and openings from more than one angle.')
add('Compare appearance at normal playing distance as well as close up. If you are testing performance, use the same scene and similar settings for both versions. Reducing clothing triangles may help, but other parts of rendering can still be the main cost.')
add('If the result is worse', 'h2')
add('Close the game and restore the original bundle and matching catalogs from your backup. Reopen the original working copy in the editor, keep more triangles or use a lower error budget, then export to a new test folder. Do not repeatedly simplify the last exported result unless that is intentional.')
add('Share the program or the clothing', 'h2')
add('To share <b>the editor</b>, send the full Portable ZIP. The recipient extracts everything and runs the EXE; the runtime must stay beside it. To share <b>an optimized clothing mod</b>, send the matching exported files together and explain the original folder name and installation location. Keep any required extra assets with the mod.')

page('9. Common problems and quick checklist')
add('The program does not start', 'h2')
add('Extract the entire Portable archive again into a writable folder. Check that the <b>runtime</b> directory is beside the EXE. Use the Windows x64 package and do not run from inside the ZIP. If the editor produces an <b>error.log</b>, include it when reporting the problem.')
add('The model is white or the texture looks different', 'h2')
add('Enable <b>Show texture</b>. A plain material can also mean the base-color texture is unavailable to the viewer, especially when it lives in another asset file. Normal maps and the game\'s special shading are not shown. This alone does not mean the export lost the texture.')
add('The result has more triangles than I requested', 'h2')
add('The target is approximate. Detail protection, seams, borders, topology and the error budget can limit reduction. Lower detail protection and Apply. If that is not enough, try Aggressive simplification (page 5). Inspect textures and edges. Zero detail protection alone does not enable aggressive mode.')
add('The garment looks inside out', 'h2')
add('<b>Face orientation</b> shows front sides blue, back sides red. <b>Flip normals outward</b> turns every inward-facing piece of the selected mesh to face away from the wearer (triangles, normals, morph normals); Reset undoes it. It is exported with the other edits.')
add('I selected Quads, but I still see triangles', 'h2')
add('Only suitable triangle pairs are displayed as four-sided outlines. Unpaired triangles remain visible. This mode never creates real quad topology or changes exported geometry.')
add('Apply or export is unavailable', 'h2')
add('Wait for the current operation to finish. Load a supported mesh before applying. Export needs an applied change; moving the slider is not enough. If no geometry changed, there may be nothing to export.')
add('Export says the catalog is missing or the folder exists', 'h2')
add('Put the matching <b>catalog*.json</b> beside the source bundle, with the rest of the mod files. For an existing output folder, choose a new parent folder. Do not overwrite the source or rename files at random to bypass an error.')
add('The mesh format is unsupported', 'h2')
add('The editor supports variable bone weights, including the hoodie example with up to eight influences per vertex. Compressed mesh geometry is a different format and is still unsupported. Non-triangle meshes and assets without readable type information may also fail. Keep the original and report the exact message with a sample file.')
add('Final checklist', 'h2')
add('Original backed up outside Mods. Correct mesh selected. Actual counts checked. Original and preview compared. Silhouette and details acceptable. Export completed. Bundle and catalogs kept together. Game closed before replacement. Morphs, fit and animation tested. Original backup retained.')

def footer(canvas, doc):
    canvas.setTitle('Clothing Mesh Editor 0.5 - A Modeller\'s Guide')
    canvas.setAuthor('Clothing Mesh Editor')
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#59675f'))
    canvas.drawString(52, A4[1] - 28, 'CLOTHING MESH EDITOR 0.5  /  MODELLER GUIDE')
    canvas.drawString(52, 28, 'English tutorial | Portable edition')
    canvas.drawRightString(A4[0] - 52, 28, str(doc.page))

doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=52, rightMargin=52,
                        topMargin=53, bottomMargin=47)
doc.build(story, onFirstPage=footer, onLaterPages=footer)
reader = PdfReader(output)
assert len(reader.pages) == 9, f'Unexpected overflow: {len(reader.pages)} pages'
for index, sheet in enumerate(reader.pages):
    text = sheet.extract_text()
    assert len(text) > 800, f'Sparse page {index + 1}'
    assert not sheet.images, 'The guide must be text-only'
print(output)
print('PASS: 9 pages, selectable English text, no images.')
