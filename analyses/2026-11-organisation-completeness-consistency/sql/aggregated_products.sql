WITH family AS (
    SELECT ods_code, anchor
    FROM UNNEST(@ods_codes) AS ods_code WITH OFFSET AS pos
    INNER JOIN UNNEST(@anchors) AS anchor WITH OFFSET AS pos
        USING (pos)
)

SELECT
    family.anchor AS ods_code,
    scmd.year_month,
    COUNT(DISTINCT scmd.vmp_code) AS n_products
FROM `ebmdatalab.scmd_pipeline.scmd_processed` AS scmd
INNER JOIN family
    ON family.ods_code = scmd.ods_code
WHERE scmd.quantity > 0
GROUP BY ods_code, year_month
