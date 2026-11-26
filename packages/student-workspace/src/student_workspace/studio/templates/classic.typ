// Classic (Harvard-style): black serif, centered name and headings, organization first.
#import "common.typ": *
#let data = resume-data()
#let s = data.settings
#let sp(x) = x * s.spacing

#show: resume-doc.with(data)
#set page(paper: "us-letter", margin: s.margin * 1in)
#set text(font: "Libertinus Serif", size: s.font_size * 1pt, lang: "en")
#set par(leading: 0.5em, spacing: 0.5em, justify: false)
#show link: it => underline(offset: 1.6pt, stroke: 0.4pt, it)

#let section(title) = block(above: sp(14pt), below: sp(5pt), width: 100%, {
  align(center, text(size: 1.05em, weight: "bold", upper(plain-text(title))))
  v(-4pt)
  line(length: 100%, stroke: 0.6pt)
})

#let bullets(items) = if items.len() > 0 {
  block(above: sp(5pt), list(
    marker: [•],
    indent: 10pt,
    body-indent: 5pt,
    spacing: sp(5pt),
    ..items.map(b => tracked(b.id, bullet-body(b))),
  ))
}

#let entry(e) = block(above: sp(4pt), below: sp(8pt), {
  // Organization (bold) | location, then role (italic) | dates.
  let swap = e.kind in ("experience", "leadership") and has(e.subtitle)
  let top = if swap { e.subtitle } else { e.title }
  let second = if swap { e.title } else { e.subtitle }
  let right1 = e.location
  let right2 = e.dates
  if not has(second) and not has(right1) {
    right1 = right2
    right2 = ""
  }
  tracked(e.id, {
    if e.url != none { link(e.url, strong(rich(top))) } else { strong(rich(top)) }
    if has(e.tech) [, #emph(rich(e.tech))]
    if has(e.details) [ | #rich(e.details)]
    h(1fr)
    rich(right1)
    if has(second) or has(right2) {
      linebreak()
      emph(rich(second))
      h(1fr)
      rich(right2)
    }
    if has(e.note) {
      linebreak()
      rich(e.note)
    }
  })
  bullets(e.bullets)
})

#align(center)[
  #block(below: sp(5pt), text(size: 1.7em, weight: "bold", rich(data.name)))
  #text(size: 0.95em, contact-line(data, " | "))
]

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
