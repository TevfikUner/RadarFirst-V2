"""
ml_veri_indir.py
-------------------
KULLANIM DIŞI. Eski ML hattı için Kuzeydoğu ABD kutusunda seçili günlerin
ERA5'ini CDS kota korumasını atlayarak indiriyordu ve hatalı irtifa
filtresiyle seçilmiş PIREP'lere hizmet ediyordu. Yerine: gece işi
(POST /api/v1/ml/gece-isi; ml/ml_veri_hatti.py), CDS kotası kod seviyesinde.
"""

from turbulans_radar.ml.turbulans_ml_modeli import ESKI_VERI_HATTI_MESAJI

raise SystemExit(ESKI_VERI_HATTI_MESAJI)
