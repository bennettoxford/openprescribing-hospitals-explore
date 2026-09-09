SELECT vmp_code, udfs, udfs_uom, unit_dose_uom, df_ind
FROM `ebmdatalab.scmd_pipeline.vmp_data`
WHERE vmp_code IN UNNEST(@vmp_codes)
