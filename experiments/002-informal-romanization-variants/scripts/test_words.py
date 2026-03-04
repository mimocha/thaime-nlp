"""80-word test set for Task 002, reconstructed from Task 001 categories.

This test set spans 7 categories: common, food, places, verbs, slang, compounds,
loanwords. Each entry includes the Thai word and the expected informal
romanizations that Thai users would plausibly type.
"""

# fmt: off
TEST_WORDS = [
    # === COMMON (15 words) ===
    {"thai": "สวัสดี",   "category": "common",    "expected_informal": ["sawatdee", "sawasdee", "sawaddee"]},
    {"thai": "ขอบคุณ",   "category": "common",    "expected_informal": ["khobkhun", "kopkhun", "kobkun"]},
    {"thai": "ครับ",     "category": "common",    "expected_informal": ["krap", "krab", "krub"]},
    {"thai": "ค่ะ",      "category": "common",    "expected_informal": ["ka", "kha", "kaa"]},
    {"thai": "ไม่",      "category": "common",    "expected_informal": ["mai", "my"]},
    {"thai": "ใช่",      "category": "common",    "expected_informal": ["chai", "chy"]},
    {"thai": "ดี",       "category": "common",    "expected_informal": ["dee", "dii"]},
    {"thai": "ไป",       "category": "common",    "expected_informal": ["pai", "bai", "py"]},
    {"thai": "มา",       "category": "common",    "expected_informal": ["ma", "maa"]},
    {"thai": "กิน",      "category": "common",    "expected_informal": ["gin", "kin"]},
    {"thai": "น้ำ",      "category": "common",    "expected_informal": ["nam", "naam", "num"]},
    {"thai": "คน",       "category": "common",    "expected_informal": ["kon", "khon"]},
    {"thai": "เขา",      "category": "common",    "expected_informal": ["khao", "kao", "kow"]},
    {"thai": "นี่",      "category": "common",    "expected_informal": ["nee", "nii"]},
    {"thai": "อะไร",     "category": "common",    "expected_informal": ["arai", "a-rai"]},

    # === FOOD (12 words) ===
    {"thai": "ข้าว",     "category": "food",      "expected_informal": ["khao", "kao", "kow"]},
    {"thai": "ผัดไท",    "category": "food",      "expected_informal": ["pad thai", "padthai", "pattai"]},
    {"thai": "ส้มตำ",    "category": "food",      "expected_informal": ["somtam", "somtum", "som tam"]},
    {"thai": "ต้มยำ",    "category": "food",      "expected_informal": ["tomyam", "tom yam", "tomyum"]},
    {"thai": "แกงเขียวหวาน", "category": "food",  "expected_informal": ["kaeng khiao wan", "gang kiaw wan", "gaeng kiew waan"]},
    {"thai": "หมู",      "category": "food",      "expected_informal": ["moo", "mu", "muu"]},
    {"thai": "ไก่",      "category": "food",      "expected_informal": ["kai", "gai", "guy"]},
    {"thai": "ปลา",      "category": "food",      "expected_informal": ["pla", "plaa", "bla"]},
    {"thai": "เส้น",     "category": "food",      "expected_informal": ["sen", "senn"]},
    {"thai": "เผ็ด",     "category": "food",      "expected_informal": ["ped", "pet", "phet"]},
    {"thai": "ก๋วยเตี๋ยว", "category": "food",    "expected_informal": ["guay tiew", "kuay tiew", "kuaitiao"]},
    {"thai": "ลาบ",      "category": "food",      "expected_informal": ["laab", "lab", "larb"]},

    # === PLACES (10 words) ===
    {"thai": "กรุงเทพ",  "category": "places",    "expected_informal": ["krungthep", "krung thep", "grungtep"]},
    {"thai": "เชียงใหม่", "category": "places",   "expected_informal": ["chiang mai", "chiangmai", "chiang my"]},
    {"thai": "ภูเก็ต",   "category": "places",    "expected_informal": ["phuket", "puket", "pooket"]},
    {"thai": "พัทยา",    "category": "places",    "expected_informal": ["pattaya", "pataya", "phatthaya"]},
    {"thai": "อยุธยา",   "category": "places",    "expected_informal": ["ayutthaya", "ayuttaya", "ayudhya"]},
    {"thai": "สุโขทัย",  "category": "places",    "expected_informal": ["sukhothai", "sukothai", "sukhotai"]},
    {"thai": "เกาะ",     "category": "places",    "expected_informal": ["koh", "ko", "kor"]},
    {"thai": "ถนน",      "category": "places",    "expected_informal": ["thanon", "tanon"]},
    {"thai": "วัด",      "category": "places",    "expected_informal": ["wat", "wad"]},
    {"thai": "ตลาด",     "category": "places",    "expected_informal": ["talad", "talat", "talaat"]},

    # === VERBS (10 words) ===
    {"thai": "พูด",      "category": "verbs",     "expected_informal": ["pood", "puut", "put"]},
    {"thai": "เขียน",    "category": "verbs",     "expected_informal": ["kian", "khian", "kiian"]},
    {"thai": "อ่าน",     "category": "verbs",     "expected_informal": ["aan", "arn"]},
    {"thai": "เรียน",    "category": "verbs",     "expected_informal": ["rian", "riian", "learn"]},
    {"thai": "ทำงาน",    "category": "verbs",     "expected_informal": ["tam ngan", "tamngan", "tamngaan"]},
    {"thai": "ซื้อ",     "category": "verbs",     "expected_informal": ["sue", "seu", "suu"]},
    {"thai": "ขาย",      "category": "verbs",     "expected_informal": ["kai", "khai", "kaai"]},
    {"thai": "รัก",      "category": "verbs",     "expected_informal": ["rak", "ruk"]},
    {"thai": "ชอบ",      "category": "verbs",     "expected_informal": ["chob", "chop", "chorb"]},
    {"thai": "หิว",      "category": "verbs",     "expected_informal": ["hiew", "hiu", "hiw"]},

    # === SLANG/INFORMAL (13 words) ===
    {"thai": "สบาย",     "category": "slang",     "expected_informal": ["sabai", "sabaai", "sa bai"]},
    {"thai": "เท่",      "category": "slang",     "expected_informal": ["teh", "te", "tay"]},
    {"thai": "อร่อย",    "category": "slang",     "expected_informal": ["aroi", "aroy", "arroy"]},
    {"thai": "สนุก",     "category": "slang",     "expected_informal": ["sanuk", "sa nuk", "sanook"]},
    {"thai": "แซ่บ",     "category": "slang",     "expected_informal": ["saeb", "saep", "zap"]},
    {"thai": "จริง",     "category": "slang",     "expected_informal": ["jing", "ching", "cing"]},
    {"thai": "เก่ง",     "category": "slang",     "expected_informal": ["keng", "geng"]},
    {"thai": "แพง",      "category": "slang",     "expected_informal": ["paeng", "pang", "phang"]},
    {"thai": "ถูก",      "category": "slang",     "expected_informal": ["took", "tuk", "thook"]},
    {"thai": "หล่อ",     "category": "slang",     "expected_informal": ["lor", "lo", "law"]},
    {"thai": "จ๊าบ",     "category": "slang",     "expected_informal": ["jab", "chab", "jaab"]},
    {"thai": "โอเค",     "category": "slang",     "expected_informal": ["ok", "oke", "okhay"]},
    {"thai": "ซิ่ง",     "category": "slang",     "expected_informal": ["sing", "zing"]},

    # === COMPOUNDS (10 words) ===
    {"thai": "โรงเรียน", "category": "compounds", "expected_informal": ["rong rian", "rongrian", "rong riian"]},
    {"thai": "โรงพยาบาล", "category": "compounds", "expected_informal": ["rong payaban", "rongpayaban", "rong pa ya ban"]},
    {"thai": "สนามบิน",  "category": "compounds", "expected_informal": ["sanam bin", "sanambin", "sa nam bin"]},
    {"thai": "มหาวิทยาลัย", "category": "compounds", "expected_informal": ["mahawitthayalai", "mahawittayalai", "maha wit ta ya lai"]},
    {"thai": "ประเทศ",   "category": "compounds", "expected_informal": ["pratet", "prathet", "prated"]},
    {"thai": "ร้านอาหาร", "category": "compounds", "expected_informal": ["raan aahaan", "ran ahan", "raan ahaan"]},
    {"thai": "ห้องน้ำ",  "category": "compounds", "expected_informal": ["hong nam", "hong naam", "hongnam"]},
    {"thai": "รถไฟ",     "category": "compounds", "expected_informal": ["rot fai", "rotfai", "rod fai"]},
    {"thai": "เมืองไทย", "category": "compounds", "expected_informal": ["muang thai", "mueangthai", "mueng tai"]},
    {"thai": "ตำรวจ",    "category": "compounds", "expected_informal": ["tamruat", "tamruat", "tamruad"]},

    # === LOANWORDS (10 words) ===
    {"thai": "แท็กซี่",  "category": "loanwords", "expected_informal": ["taxi", "taksi", "teksee"]},
    {"thai": "อินเทอร์เน็ต", "category": "loanwords", "expected_informal": ["internet", "intanet", "inthoenet"]},
    {"thai": "คอมพิวเตอร์", "category": "loanwords", "expected_informal": ["computer", "kom piw ter", "khomphiuter"]},
    {"thai": "โทรศัพท์", "category": "loanwords", "expected_informal": ["thorasap", "torasap", "torasub"]},
    {"thai": "เฟซบุ๊ก",  "category": "loanwords", "expected_informal": ["facebook", "fesabuk", "fesbuk"]},
    {"thai": "กาแฟ",     "category": "loanwords", "expected_informal": ["kafae", "cafe", "kafee"]},
    {"thai": "ช็อกโกแลต", "category": "loanwords", "expected_informal": ["chocolate", "chokkolat", "chokkolaet"]},
    {"thai": "แฮมเบอร์เกอร์", "category": "loanwords", "expected_informal": ["hamburger", "hamberger", "haemboekoe"]},
    {"thai": "เบียร์",   "category": "loanwords", "expected_informal": ["beer", "bia", "beer"]},
    {"thai": "ฟุตบอล",   "category": "loanwords", "expected_informal": ["football", "futbon", "fut bon"]},
]
# fmt: on

assert len(TEST_WORDS) == 80, f"Expected 80 words, got {len(TEST_WORDS)}"
