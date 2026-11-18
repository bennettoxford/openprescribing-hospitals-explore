SELECT
    ods_code,
    ods_name,
    ARRAY_TO_STRING(successors, "|") AS successors,
    ARRAY_TO_STRING(ultimate_successors, "|") AS ultimate_successors,
    ARRAY_TO_STRING(predecessors, "|") AS predecessors,
    legal_closed_date,
    operational_closed_date,
    legal_open_date,
    operational_open_date
FROM `ebmdatalab.scmd_pipeline.ods`
