import uuid
from datetime import datetime, timezone


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _rid():
    return str(uuid.uuid4())


U = "https://images.unsplash.com/"
Q = "?crop=entropy&cs=srgb&fm=jpg&q=85&w=1100"

IMG = {
    "olymp_a": U + "photo-1652305500057-0fcb348b62aa" + Q,
    "olymp_b": U + "photo-1719159381916-062fa9f435a6" + Q,
    "olymp_c": U + "photo-1761208662734-fb46f1398551" + Q,
    "olymp_d": U + "photo-1573894999291-f440466112cc" + Q,
    "corp_a": U + "photo-1758518731468-98e90ffd7430" + Q,
    "corp_b": U + "photo-1758691736548-073bc97cdff4" + Q,
    "corp_c": U + "photo-1758691736067-b309ee3ef7b9" + Q,
    "corp_d": U + "photo-1758691736433-4078b93abd72" + Q,
    "award_a": U + "photo-1665680674724-3a3b3368e036" + Q,
    "award_b": U + "photo-1667967699372-1c26d40dec46" + Q,
    "award_c": U + "photo-1625643268477-838321f445bb" + Q,
    "team_a": U + "photo-1500648767791-00dcc994a43e" + Q,
    "team_b": U + "photo-1573497019940-1c28c88b4f3e" + Q,
    "team_c": U + "photo-1504257432389-52343af06ae3" + Q,
    "team_d": U + "photo-1506863530036-1efeddceb993" + Q,
    "about": U + "photo-1761208662734-fb46f1398551" + Q,
    "map": U + "photo-1524661135-423995f22d0b" + Q,
    "hero": U + "photo-1758685845872-4edbf0e76014" + Q,
}


def _team():
    data = [
        ("Dr. Arya Wibawa", "Direktur Akademik & Pakar Kompetensi Eksakta",
         "Merancang blueprint pembinaan olimpiade yang telah mengantar ratusan siswa ke panggung nasional.", IMG["team_a"]),
        ("Sinta Larasati, M.Sc.", "Kepala Kurikulum & Silabus",
         "Menerjemahkan konsep kompleks menjadi modul pembelajaran yang terstruktur dan terukur.", IMG["team_b"]),
        ("Reza Adiputra", "Instruktur Logika & Pemrograman",
         "Membangun nalar algoritmik siswa lewat pendekatan problem-solving yang menantang.", IMG["team_c"]),
        ("Maya Prawira", "Lead Corporate Training (B2B)",
         "Mendesain program upskilling SDM yang berdampak langsung pada performa organisasi.", IMG["team_d"]),
    ]
    return [{"id": _rid(), "name": n, "role": r, "desc": d, "image_url": img, "order": i, "created_at": _iso()}
            for i, (n, r, d, img) in enumerate(data)]


def _services():
    data = [
        ("Trophy", "Pelatihan Intensif Olimpiade",
         "Pembinaan terarah untuk kompetisi logika, matematika, dan sains eksakta dengan mentor berpengalaman dan sistem tryout berkala.",
         ["Kurikulum bertingkat", "Simulasi kompetisi", "Analisis performa personal"]),
        ("BookOpenCheck", "Pengembangan Kurikulum & Silabus",
         "Penyusunan modul, silabus, dan blueprint pembelajaran yang terukur untuk sekolah maupun lembaga pendidikan mitra.",
         ["Modul berbasis kompetensi", "Blueprint asesmen", "Pendampingan implementasi"]),
        ("Building2", "B2B Corporate Training & Sertifikasi",
         "Program upskilling SDM korporat untuk memaksimalkan potensi tim, dilengkapi asesmen dan sertifikasi resmi.",
         ["Analisis kebutuhan", "Pelatihan tailor-made", "Sertifikasi terukur"]),
    ]
    return [{"id": _rid(), "icon": ic, "title": t, "desc": d, "points": p, "order": i, "created_at": _iso()}
            for i, (ic, t, d, p) in enumerate(data)]


def _partners():
    names = ["TELKOM", "ASTRA", "PERTAMINA", "BCA", "GOJEK", "MANDIRI", "PLN", "UNILEVER"]
    return [{"id": _rid(), "name": n, "logo_url": "", "order": i, "created_at": _iso()} for i, n in enumerate(names)]


def _stats():
    data = [(1200, "+", "Siswa Terlatih"), (65, "+", "Perusahaan Mitra"),
            (140, "+", "Modul & Blueprint"), (320, "+", "Prestasi Diraih")]
    return [{"id": _rid(), "value": v, "suffix": s, "label": l, "order": i, "created_at": _iso()}
            for i, (v, s, l) in enumerate(data)]


def _albums():
    data = [
        ("Pembinaan Olimpiade", "Kelas intensif menuju kompetisi nasional",
         IMG["olymp_b"], [IMG["olymp_b"], IMG["olymp_a"], IMG["olymp_c"], IMG["olymp_d"]]),
        ("Corporate Training", "Program upskilling untuk perusahaan mitra",
         IMG["corp_b"], [IMG["corp_b"], IMG["corp_a"], IMG["corp_c"], IMG["corp_d"]]),
        ("Penganugerahan Juara", "Momen kemenangan siswa binaan kami",
         IMG["award_a"], [IMG["award_a"], IMG["award_b"], IMG["award_c"]]),
        ("Kegiatan & Event", "Workshop, seminar, dan kolaborasi",
         IMG["corp_c"], [IMG["corp_c"], IMG["olymp_c"], IMG["corp_d"], IMG["olymp_a"]]),
    ]
    return [{"id": _rid(), "title": t, "subtitle": s, "cover_url": c, "photos": p, "order": i, "created_at": _iso()}
            for i, (t, s, c, p) in enumerate(data)]


def _settings():
    return {
        "_key": "site",
        "hero_badge": "PT Skena Pendidikan Berprestasi",
        "hero_title": "Mencapai Prestasi Tertinggi & Memaksimalkan Potensi SDM",
        "hero_highlight": "Tertinggi",
        "hero_highlight2": "SDM",
        "hero_subtitle": "Binara Labs adalah katalisator juara. Kami membina siswa menuju olimpiade logika eksakta, sekaligus merancang program corporate training yang mentransformasi kompetensi tim Anda.",
        "hero_image": IMG["hero"],
        "about_heading": "Katalisator para juara & profesional.",
        "about_paragraph": "Di bawah naungan PT Skena Pendidikan Berprestasi, Binara Labs memadukan ketajaman akademik dan disiplin industri. Kami tidak sekadar mengajar — kami membangun cara berpikir yang membedakan pemenang dari peserta.",
        "about_image": IMG["about"],
        "contact_address": "Gedung Skena, Jl. Prestasi No. 21, Jakarta Selatan",
        "contact_email": "halo@binaralabs.id",
        "contact_phone": "+62 21 5000 8899",
        "whatsapp_number": "6285000088990",
        "map_embed": "Jl. Jenderal Sudirman, Jakarta Selatan, Indonesia",
        "map_image": IMG["map"],
        "social_instagram": "#",
        "social_linkedin": "#",
        "social_twitter": "#",
        "social_youtube": "#",
    }


def _categories():
    data = [
        ("Siswa", "GraduationCap", "Untuk siswa yang ingin mengikuti pembinaan olimpiade & kompetisi logika eksakta."),
        ("Perusahaan", "Building2", "Untuk perusahaan/instansi yang membutuhkan corporate training & sertifikasi SDM."),
    ]
    return [{"id": _rid(), "label": l, "icon": ic, "desc": d, "order": i, "created_at": _iso()}
            for i, (l, ic, d) in enumerate(data)]


async def seed_content(db):
    if await db.team.count_documents({}) == 0:
        await db.team.insert_many(_team())
    if await db.categories.count_documents({}) == 0:
        await db.categories.insert_many(_categories())
    if await db.services.count_documents({}) == 0:
        await db.services.insert_many(_services())
    if await db.partners.count_documents({}) == 0:
        await db.partners.insert_many(_partners())
    if await db.stats.count_documents({}) == 0:
        await db.stats.insert_many(_stats())
    if await db.albums.count_documents({}) == 0:
        await db.albums.insert_many(_albums())
    if await db.settings.count_documents({"_key": "site"}) == 0:
        await db.settings.insert_one(_settings())
    await db.settings.update_one(
        {"_key": "site", "whatsapp_number": {"$exists": False}},
        {"$set": {"whatsapp_number": "6285000088990"}},
    )
