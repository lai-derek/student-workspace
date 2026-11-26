// Jake-style: serif, navy headings over a thin rule, dates on the right.
#import "common.typ": *
#let data = resume-data()
#let s = data.settings
#let sp(x) = x * s.spacing
#let navy = rgb(18, 63, 112)
#let rule-color = rgb(166, 176, 188)

#show: resume-doc.with(data)
#set page(paper: "us-letter", margin: s.margin * 1in)
#set text(font: "New Computer Modern", size: s.font_size * 1pt, lang: "en")
#set par(leading: 0.5em, spacing: 0.5em, justify: false)
#show link: it => underline(offset: 1.8pt, stroke: 0.4pt, it)

#let section(title) = block(above: sp(17pt), below: sp(4pt), {
  text(size: 1.15em, weight: "bold", fill: navy, rich(title))
  v(-3.5pt)
  line(length: 100%, stroke: 0.5pt + rule-color)
})

#let bullets(items) = if items.len() > 0 {
  block(above: sp(7pt), list(
    marker: [•],
    indent: 1pt,
    body-indent: 6pt,
    spacing: sp(7pt),
    ..items.map(b => tracked(b.id, bullet-body(b))),
  ))
}

#let entry(e) = block(above: sp(4pt), below: sp(9pt), {
  // Education: school | location, then degree | dates. Others: title | dates, then subtitle | location.
  let right1 = if e.kind == "education" { e.location } else { e.dates }
  let right2 = if e.kind == "education" { e.dates } else { e.location }
  if not has(right1) and not has(e.subtitle) {
    right1 = right2
    right2 = ""
  }
  tracked(e.id, {
    if e.url != none { link(e.url, strong(rich(e.title))) } else { strong(rich(e.title)) }
    if has(e.tech) [ | #emph(rich(e.tech))]
    if has(e.details) [ | #rich(e.details)]
    h(1fr)
    rich(right1)
    if has(e.subtitle) or has(right2) {
      linebreak()
      emph(rich(e.subtitle))
      h(1fr)
      // Education dates are italic; a location stays upright.
      if e.kind == "education" { emph(rich(right2)) } else { rich(right2) }
    }
    if has(e.note) {
      linebreak()
      rich(e.note)
    }
  })
  bullets(e.bullets)
})

#align(center)[
  #block(below: sp(6pt), text(size: 2.4em, weight: "bold", fill: navy, rich(data.name)))
  #text(size: 0.95em, contact-line(data, " | "))
]
#v(sp(5pt))

#for sec in data.sections {
  section(sec.title)
  for e in sec.entries { entry(e) }
}

#if data.skills.len() > 0 {
  section("Technical Skills")
  for sk in data.skills [
    #strong[#rich(sk.label):] #rich(sk.value) \
  ]
}

#positions()
