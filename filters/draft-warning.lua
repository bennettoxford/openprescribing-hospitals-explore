local function is_draft(meta)
  if not meta.categories then
    return false
  end

  for _, category in ipairs(meta.categories) do
    if pandoc.utils.stringify(category):lower() == "draft" then
      return true
    end
  end

  return false
end

function Pandoc(doc)
  if not is_draft(doc.meta) then
    return doc
  end

  local warning = quarto.Callout({
    type = "warning",
    title = "Draft report",
    content = {
      pandoc.Para({
        pandoc.Str("This report is a work in progress. It may be incomplete or contain errors."),
      }),
    },
  })
  table.insert(doc.blocks, 1, warning)
  return doc
end
