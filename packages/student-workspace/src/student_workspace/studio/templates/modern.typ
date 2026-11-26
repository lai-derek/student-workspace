// Modern: sans-serif, left-aligned name, teal small-caps headings without rules.
// Uses a Windows sans font when present; Typst falls back to its bundled fonts.
#import "common.typ": *
#let data = resume-data()
#let s = data.settings
#let sp(x) = x * s.spacing
#let accent = rgb(15, 118, 110)
#let muted = rgb(85, 85, 85)

#show: resume-doc.with(data)
#set page(paper: "us-letter", margin: s.margin * 1in)
#set text(font: ("Segoe UI", "Calibri", "Arial", "Libertinus Serif"), size: s.font_size * 0.95pt, lang: "en")
#set par(leading: 0.55em, spacing: 0.55em, justify: false)
#show link: it => underline(offset: 1.6pt, stroke: 0.4pt + accent, it)

#let section(title) = block(above: sp(15pt), below: sp(6pt), {
  text(size: 0.95em, weight: "bold", fill: accent, tracking: 0.08em, upper(plain-text(title)))
})

#let bullets(items) = if items.len() > 0 {
  block(above: sp(5pt), list(
    marker: text(fill: accent)[•],
    indent: 2pt,
    body-indent: 6pt,
    spacing: sp(5pt),
    ..items.map(b => tracked(b.id, bullet-body(b))),
  ))
}

#let entry(e) = block(above: sp(4pt), below: sp(9pt), {
  tracked(e.id, {
    if e.url != none { link(e.url, strong(rich(e.title))) } else { strong(rich(e.title)) }
    if has(e.tech) [#text(fill: muted)[ · #rich(e.tech)]]
    if has(e.details) [ · #rich(e.details)]
    h(1fr)
    text(fill: muted, rich(e.dates))
    let second = ()
    if has(e.subtitle) { second.push(emph(rich(e.subtitle))) }
    if has(e.location) { second.push(rich(e.location)) }
    if second.len() > 0 {
      linebreak()
      text(fill: muted, second.join(" · "))
    }
    if has(e.note) {
      linebreak()
      rich(e.note)
    }
  })
  bullets(e.bullets)
})

#block(below: sp(4pt), text(size: 2.2em, weight: "bold", fill: accent, rich(data.name)))
#text(fill: muted, contact-line(data, "  |  "))
#v(sp(2pt))

#for sec in data.sections {
  section(sec.title)
  for e in sec.entries { entry(e) }
}

#if data.skills.len() > 0 {
  section("Skills")
  for sk in data.skills [
    #strong[#rich(sk.label):] #rich(sk.value) \
  ]
}

#positions()
