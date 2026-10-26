SELECT DISTINCT
  vmp.id AS vmp_id,
  vmp.nm AS vmp_nm,
  vmp.invalid AS invalid_vmp,
  vtm.id AS vtm_id,
  vtm.nm AS vtm_nm,
  ofr.descr AS form,
  ARRAY_TO_STRING(vmpdata.who_route_codes_for_ddd, "|") AS who_route_codes_for_ddd,
  (
    SELECT atc.atc_code
    FROM UNNEST(vmpdata.atcs) AS atc
    LIMIT 1
  ) AS atc
FROM `ebmdatalab.dmd.vmp` vmp
LEFT JOIN dmd.ont ont ON vmp.id = ont.vmp
LEFT JOIN dmd.vtm vtm ON vmp.vtm = vtm.id
LEFT JOIN dmd.ontformroute ofr ON ont.form = ofr.cd
LEFT JOIN `ebmdatalab.scmd_pipeline.vmp_data` vmpdata
  ON CAST(vmp.id AS STRING) = vmpdata.vmp_code
