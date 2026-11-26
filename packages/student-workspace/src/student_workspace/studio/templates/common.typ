// Shared by every resume template: data loading, rich text, click-to-edit markers.
// Resume text arrives as segment lists ({text, bold, italic, url}) and is inserted
// as plain text, so nothing a student types is run as Typst code. Only a bullet's
// "raw" field (an advanced override the student writes on purpose) is evaluated.

#let resume-data() = {
  let raw = sys.inputs.at("data-json", default: none)
  if raw == none { panic("no resume data: compile this template through the studio") }
  json(bytes(raw))
}

#let rich(value) = if type(value) == str { value } else if value.len() == 0 { [] } else {
  value.map(s => {
    let c = [#s.text]
    if s.bold { c = strong(c) }
    if s.italic { c = emph(c) }
    if s.url != none { c = link(s.url, c) }
    c
  }).join()
}

#let plain-text(value) = if type(value) == str { value } else if value.len() == 0 { "" } else { value.map(s => s.text).join() }

#let has(value) = if value == none { false } else if type(value) == str { value != "" } else { value.len() > 0 }

// Invisible markers before and after an editable element; their page positions
// tell the preview which bullet or entry was clicked.
#let tracked(id, body) = [#metadata(id)<sw-s>#body#metadata(id)<sw-e>]

#let bullet-body(b) = if b.raw != none { eval(b.raw, mode: "markup") } else { rich(b.text) }

// Document metadata, with the date fixed by the version so the same source
// always produces the same PDF bytes.
#let resume-doc(data, body) = {
  let parts = data.date.split("-").map(int)
  set document(
    title: plain-text(data.name) + " - Resume",
    author: plain-text(data.name),
    date: datetime(year: parts.at(0), month: parts.at(1), day: parts.at(2)),
  )
  body
}

#let contact-line(data, sep) = {
  let items = data.contact.map(c => if c.url != none { link(c.url, rich(c.text)) } else { rich(c.text) })
  if items.len() > 0 { items.join(sep) } else { [] }
}

// Where every marker landed, plus where the content ends (for the page-fill meter).
#let positions() = context {
  let pos(m) = {
    let p = m.location().position()
    (id: m.value, page: p.page, x: p.x.pt(), y: p.y.pt())
  }
  let here-pos = here().position()
  [#metadata((
    starts: query(<sw-s>).map(pos),
    ends: query(<sw-e>).map(pos),
    end: (page: here-pos.page, y: here-pos.y.pt()),
    pages: counter(page).final().first(),
    page-width: page.width.pt(),
    page-height: page.height.pt(),
  ))<sw-positions>]
}
