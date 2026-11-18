SELECT
    file_type,
    MIN(year_month) AS min_month,
    MAX(year_month) AS max_month
FROM `ebmdatalab.scmd_pipeline.scmd_data_status`
GROUP BY file_type
