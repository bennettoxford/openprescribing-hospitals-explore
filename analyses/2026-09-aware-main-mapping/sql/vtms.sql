SELECT
  vtm.id,
  vtm.nm
FROM `ebmdatalab.dmd.vtm` vtm
WHERE vtm.invalid IS NOT TRUE
