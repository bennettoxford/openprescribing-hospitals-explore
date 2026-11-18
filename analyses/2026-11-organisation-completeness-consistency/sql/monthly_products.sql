SELECT
    ods_code,
    year_month,
    COUNT(DISTINCT vmp_code) AS n_products
FROM `ebmdatalab.scmd_pipeline.scmd_processed`
WHERE quantity > 0
GROUP BY ods_code, year_month
