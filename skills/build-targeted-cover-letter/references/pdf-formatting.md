# PDF, LaTeX, and color decisions

Checked November 10, 2026. Apply these recommendations to cover letters, preserving an accepted baseline. Most ATS evidence below concerns resumes; applying the same text/layout precautions to letters is a practical inference, not confirmation that a particular employer parses letters.

## Choose the output, not an authoring-tool reputation

PDF and Word are supported by [Lever's resume parser](https://help.lever.co/s/article/Understanding-Resume-Parsing), while image formats cannot be parsed. Lever suggests highlighting text as an initial check. This does not establish that every selectable document parses correctly, that cover letters enter its resume parser, or that DOCX always outperforms PDF. The reviewed vendor guidance does not establish a blanket penalty for LaTeX-produced PDFs. Keep LaTeX when suitable; judge the actual exported document and the application's accepted formats. Submit the PDF, not the `.tex` source, unless asked for source.

[Adobe's PDF accessibility guidance](https://helpx.adobe.com/acrobat/using/accessibility-features-pdfs.html) distinguishes searchable text, font-to-Unicode extraction, and logical reading order. A document can look correct but copy as incorrect characters. [Adobe's font-embedding guidance](https://helpx.adobe.com/acrobat/desktop/create-documents/explore-advanced-conversion-settings/font-handling-distiller.html) explains that embedded fonts or embedded subsets preserve appearance across systems. Embedding and usable text mapping are different properties; neither alone proves ATS compatibility.

Prefer normal readable fonts and embed them where supported. Do not impose an unverified Arial/Times whitelist or reject an established LaTeX font by name. Preserve a working font/compiler setup. Investigate missing glyphs or failed extraction with existing PDF font/text tools when needed. Do not paste engine-specific Unicode primitives, disable ligatures/kerning globally, or rebuild the layout because an online ATS recipe recommends it. Make a targeted fix for a diagnosed problem, compile with the actual installed engine, and inspect the new PDF.

PDF tags can improve accessibility; no reviewed ATS source established PDF/UA, PDF/A, or a tagged-PDF flag as a universal application requirement. Do not claim those flags certify ATS compatibility or switch toolchains solely to obtain them.

## Color, links, and layout

The reviewed [Greenhouse parsing guidance](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse) identifies images, letter spacing, complex tables, columns, and headers/footers as potential problems. It does not state a blanket ban on colored text. Do not claim either that color causes rejection or that every use of color is harmless.

Use black body text on white and retain a restrained existing navy or other dark accent for the name/heading when matching the resume. [Adobe's color-contrast guidance](https://helpx.adobe.com/acrobat/using/create-verify-pdf-accessibility.html) concerns readability and accessibility, not an ATS score. Inspect the document in grayscale: contact details, headings, and rules should remain legible. Do not use pale body text, colored panels, decorative charts, or color as the sole way to convey meaning. These are readability defaults, not a new requirement to recolor an accepted resume.

Keep meaningful text in the normal body. A visual contact heading is not the same as a running page header. Prefer ordinary one-column paragraphs for the letter. Avoid copying resume alignment tables into prose; an existing `tabular` command is a risk to inspect, not proof of failure or authorization to redesign the resume. Bold/italic emphasis and ordinary hyperlinks need no blanket removal when text and order remain intact. Underline the full visible link title consistently with the resume. Make the email and useful contact URL/user name visible in text, not only an icon or a hidden URI annotation.

## Check the saved artifact proportionately

When checks are permitted, inspect extracted text for the name, email/contact text, employer, exact role, key technical terms, and the body paragraphs in order. Check problematic glyphs in actual content, including ligatures, punctuation, or accented names when present. Check link annotations separately; visible link text and a clickable destination are different checks. Reject genuinely missing text, character corruption, or interleaved paragraphs until repaired or disclosed.

[pypdf's extraction documentation](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) explains ambiguities around whitespace, ligatures, positioned text, and links. Do not demand identical line breaks or byte-for-byte output. If one extractor shows an oddity, compare with the source and a viewer's copy/paste or another available extractor before changing typography. Normalizing a ligature for comparison does not justify overlooking a genuinely broken word. A passing extraction check is a local sanity check, not a simulation of the employer's ATS.

Verify the file opens without a password and is within the actual upload field's limit. Upload acceptance limits, resume parser limits, and limits on a custom attachment are different. For example, [Workable's upload documentation](https://help.workable.com/hc/en-us/articles/115012238108-What-types-of-files-can-be-uploaded-on-the-application-form) gives different limits for resumes and custom-question attachments. Avoid a universal cap or unnecessary image compression/flattening of an already small text document. Retain the current skill's full-page and detail-crop visual inspection after the final edit; do not substitute extraction, font embedding, or an online score for that inspection.
