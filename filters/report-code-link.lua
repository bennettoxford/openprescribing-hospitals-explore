function Pandoc(doc)
  local path = quarto.doc.input_file:gsub("\\", "/")
  local folder = path:match("(analyses/[^_/][^/]*)/")

  if folder then
    local url = "https://github.com/bennettoxford/openprescribing-hospitals-explore/tree/main/" .. folder
    local link = pandoc.Link("View source code on GitHub", url)
    table.insert(doc.blocks, 1, pandoc.Para({ link }))
  end

  return doc
end
