from sqlalchemy import func, select
from sqlalchemy.orm import Session

from turbulans_radar.depo.models import KullaniciGeriBildirimi
from turbulans_radar.depo.veritabani import motor_al


def geri_bildirim_kaydet(
    hedef_turu: str,
    rol: str,
    hedef_kimligi: str | None = None,
    yararli_mi: bool | None = None,
    dogru_mu: bool | None = None,
    aciklama: str | None = None,
    yazilim_surumu: str | None = None,
    motor=None,
) -> int:
    with Session(motor or motor_al()) as oturum:
        kayit = KullaniciGeriBildirimi(
            hedef_turu=hedef_turu,
            hedef_kimligi=hedef_kimligi,
            yararli_mi=yararli_mi,
            dogru_mu=dogru_mu,
            aciklama=aciklama,
            rol=rol,
            yazilim_surumu=yazilim_surumu,
        )
        oturum.add(kayit)
        oturum.commit()
        return int(kayit.id)


def geri_bildirim_ozeti(motor=None) -> dict:
    model = KullaniciGeriBildirimi
    sorgu = select(
        model.hedef_turu,
        func.count(),
        func.count(model.yararli_mi),
        func.count().filter(model.yararli_mi.is_(True)),
        func.count(model.dogru_mu),
        func.count().filter(model.dogru_mu.is_(True)),
    ).group_by(model.hedef_turu)
    with Session(motor or motor_al()) as oturum:
        satirlar = oturum.execute(sorgu).all()
    return {
        hedef: {
            "toplam": int(toplam),
            "yararli_yanitlayan": int(yararli_n),
            "yararli_evet": int(yararli_evet),
            "dogru_yanitlayan": int(dogru_n),
            "dogru_evet": int(dogru_evet),
        }
        for hedef, toplam, yararli_n, yararli_evet, dogru_n, dogru_evet in satirlar
    }
