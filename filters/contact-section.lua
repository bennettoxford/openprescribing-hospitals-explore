function Pandoc(doc)
  local path = quarto.doc.input_file:gsub("\\", "/")
  local folder = path:match("(analyses/[^_/][^/]*)/")

  if folder then
    local email = "bennett@phc.ox.ac.uk"
    table.insert(
      doc.blocks,
      pandoc.Header(2, { pandoc.Str("Contact") }, pandoc.Attr("contact"))
    )
    table.insert(doc.blocks, pandoc.Para({
      pandoc.Str("If you have any questions or feedback about this report, please contact us at "),
      pandoc.Link(email, "mailto:" .. email),
      pandoc.Str("."),
    }))
  end

  return doc
end
