"""Generates an honest, small multilingual test suite for the top languages.

Replaces the previous generator, which produced 1,100 tests from ~12 templates
per language with counter numbers ("Sentence 1 regarding X."), pasted a single
foreign word into an English carrier sentence for "segmentation" cases, and had
atom tests that accepted an `expected_metric` parameter but never asserted it.

This generator instead writes real, grammatical native-language sentences
(hand-authored, not templated placeholders) for each language, using native
punctuation (。！？ for CJK, ؟۔ for Arabic, ।॥ for Devanagari, etc). Per
language it covers, in ~17 distinct cases:
  1. Native sentence segmentation (4 cases): multi-sentence native passages with
     a known correct sentence count.
  2. Atom extraction (6 cases): real carrier sentences embedding a CVE, an IPv4
     address, and a latency metric - asserting all three are detected, not just
     one.
  3. Negation detection (3 cases): real native negation sentences, asserting the
     negation is picked up by ContextCull's negation atom detector where the
     detector supports it (kind "negation" for the Western/Hebrew/Cyrillic/
     Devanagari/Bengali/Arabic word list, kind "bound_negation" for the
     CJK-specific detector used by Chinese). Japanese negation is grammatical
     inflection (...ない), which neither detector covers, so the Japanese case
     asserts the negation clause survives compilation byte-for-byte instead of
     asserting an atom kind that doesn't apply.
  4. Byte-exact UTF-8 span round-trip (3 cases): reused from the atom-extraction
     sentences, verifying clean_char_to_byte_span decodes back to the exact
     source character across multi-byte boundaries.
  5. End-to-end compile on a slice of that language's real corpus file (1 case):
     asserts status OK, output strictly smaller than input, and a byte-exact
     SourceMap round trip on the real prose (not synthetic sentences).

IPs are ordinary private-range addresses (10.x.x.x) placed with clear word
boundaries in the surrounding native prose, not version-like numbers, per the
note that other agents are independently tightening the IPv4/git-SHA atom
regexes and sentence segmentation - these tests exercise realistic input, not
edge cases those changes are meant to fix.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests" / "multilingual"
TESTS_DIR.mkdir(parents=True, exist_ok=True)
CORPUS_DIR = "examples/eval/multilingual"

# Each language: 3 carrier sentence templates (with {ip}/{cve}/{metric} placeholders,
# always surrounded by whitespace so the atom regexes' \b boundaries land correctly
# even in scripts where Unicode letters count as \w), 4 segmentation (text, count)
# pairs, 3 negation sentences, the negation atom kind this language's negation
# words are detected under ("negation", "bound_negation", or None), and the real
# corpus file to slice for the end-to-end case.
LANG_CONFIGS = {
    "en": {
        "name": "English",
        "code": "en",
        "corpus_file": "01_en_literature_alice.txt",
        "negation_kind": "negation",
        "carriers": [
            "The production server at {ip} raised an alert after CPU usage reached {metric}, and the team is tracking it under {cve}.",
            "Engineers linked the {metric} latency spike on host {ip} to the vulnerability {cve}.",
            "A patch for {cve} was deployed to {ip}, restoring throughput above {metric}.",
        ],
        "segmentation": [
            ("The database restarted cleanly. No errors were logged during the restart.", 2),
            (
                "Traffic peaked at nine in the morning. The team scaled the cluster. Latency returned to normal within minutes.",
                3,
            ),
            ("Is the backup complete? The dashboard still shows it running.", 2),
            ("Deploy the patch now! Verify the health check afterward.", 2),
        ],
        "negations": [
            "No data loss occurred during the failover.",
            "The service cannot restart without a valid configuration file.",
            "We never observed packet loss on that link.",
        ],
    },
    "zh": {
        "name": "Chinese",
        "code": "zh",
        "corpus_file": "03_zh_journey_to_the_west.txt",
        "negation_kind": "bound_negation",
        "carriers": [
            "生产服务器 {ip} 在CPU使用率达到 {metric} 后发出警报，团队正在通过 {cve} 跟踪此事件。",
            "工程师将主机 {ip} 上 {metric} 的延迟峰值与漏洞 {cve} 联系起来。",
            "针对 {cve} 的补丁已部署到 {ip}，吞吐量恢复到 {metric} 以上。",
        ],
        "segmentation": [
            ("数据库已顺利重启。重启过程中没有记录任何错误。", 2),
            ("流量在上午九点达到峰值。团队扩展了集群。延迟在几分钟内恢复正常。", 3),
            ("备份完成了吗？仪表盘仍然显示它在运行。", 2),
            ("现在部署补丁！之后请验证健康检查。", 2),
        ],
        "negations": [
            "故障转移期间没有数据丢失。",
            "服务器在未获授权的情况下无法访问数据库。",
            "该链路从未出现丢包现象。",
        ],
    },
    "hi": {
        "name": "Hindi",
        "code": "hi",
        "corpus_file": "04_hi_premchand_stories.txt",
        # Devanagari vowel signs/anusvara (matras) are Unicode combining marks, which
        # Python's \b treats as non-word chars - so a plain \b<word>\b match (kind
        # "negation") fails whenever the negation word ends in a matra (नहीं, बिना).
        # BOUND_NEGATION_RE only needs \b at the *start* of the negation word (it's
        # followed by \s+ instead of a trailing \b), so it reliably fires instead.
        "negation_kind": "bound_negation",
        "carriers": [
            "उत्पादन सर्वर {ip} पर CPU उपयोग {metric} तक पहुंचने के बाद चेतावनी जारी हुई, टीम इसे {cve} के तहत ट्रैक कर रही है।",
            "इंजीनियरों ने होस्ट {ip} पर {metric} विलंबता वृद्धि को भेद्यता {cve} से जोड़ा।",
            "{cve} के लिए पैच {ip} पर तैनात किया गया, थ्रूपुट {metric} से ऊपर बहाल हुआ।",
        ],
        "segmentation": [
            ("डेटाबेस सफलतापूर्वक पुनः आरंभ हुआ। पुनः आरंभ के दौरान कोई त्रुटि दर्ज नहीं हुई।", 2),
            (
                "सुबह नौ बजे ट्रैफ़िक चरम पर पहुंचा। टीम ने क्लस्टर को बड़ा किया। कुछ ही मिनटों में विलंबता सामान्य हो गई।",
                3,
            ),
            ("क्या बैकअप पूरा हो गया है? डैशबोर्ड अभी भी दिखा रहा है कि यह चल रहा है।", 2),
            ("अभी पैच तैनात करें! बाद में स्वास्थ्य जांच सत्यापित करें।", 2),
        ],
        "negations": [
            "फेलओवर के दौरान कोई डेटा हानि नहीं हुई।",
            "वैध कॉन्फ़िगरेशन फ़ाइल के बिना सेवा पुनः आरंभ नहीं हो सकती।",
            "उस लिंक पर हमने कभी पैकेट हानि नहीं देखी।",
        ],
    },
    "es": {
        "name": "Spanish",
        "code": "es",
        "corpus_file": "05_es_don_quijote.txt",
        "negation_kind": "negation",
        "carriers": [
            "El servidor de producción {ip} emitió una alerta después de que el uso de CPU alcanzara {metric}, y el equipo lo está rastreando bajo {cve}.",
            "Los ingenieros relacionaron el pico de latencia de {metric} en el host {ip} con la vulnerabilidad {cve}.",
            "Se implementó un parche para {cve} en {ip}, restaurando el rendimiento por encima de {metric}.",
        ],
        "segmentation": [
            (
                "La base de datos se reinició correctamente. No se registraron errores durante el reinicio.",
                2,
            ),
            (
                "El tráfico alcanzó su punto máximo a las nueve de la mañana. El equipo escaló el clúster. La latencia volvió a la normalidad en minutos.",
                3,
            ),
            (
                "¿Se completó la copia de seguridad? El panel todavía muestra que se está ejecutando.",
                2,
            ),
            ("¡Implemente el parche ahora! Verifique el chequeo de salud después.", 2),
        ],
        "negations": [
            "No se produjo pérdida de datos durante la conmutación por error.",
            "El servicio no puede reiniciarse sin un archivo de configuración válido.",
            "Nunca observamos pérdida de paquetes en ese enlace.",
        ],
    },
    "fr": {
        "name": "French",
        "code": "fr",
        "corpus_file": "06_fr_tour_du_monde.txt",
        "negation_kind": "negation",
        "carriers": [
            "Le serveur de production {ip} a déclenché une alerte après que l'utilisation du CPU a atteint {metric}, et l'équipe le suit sous {cve}.",
            "Les ingénieurs ont relié le pic de latence de {metric} sur l'hôte {ip} à la vulnérabilité {cve}.",
            "Un correctif pour {cve} a été déployé sur {ip}, restaurant le débit au-dessus de {metric}.",
        ],
        "segmentation": [
            (
                "La base de données a redémarré proprement. Aucune erreur n'a été enregistrée pendant le redémarrage.",
                2,
            ),
            (
                "Le trafic a culminé à neuf heures du matin. L'équipe a fait évoluer le cluster. La latence est revenue à la normale en quelques minutes.",
                3,
            ),
            (
                "La sauvegarde est-elle terminée ? Le tableau de bord indique toujours qu'elle est en cours.",
                2,
            ),
            ("Déployez le correctif maintenant ! Vérifiez le contrôle de santé ensuite.", 2),
        ],
        "negations": [
            "Aucune perte de données ne s'est produite pendant le basculement.",
            "Le service ne peut pas redémarrer sans un fichier de configuration valide.",
            "Nous n'avons jamais observé de perte de paquets sur ce lien.",
        ],
    },
    "ar": {
        "name": "Arabic",
        "code": "ar",
        "corpus_file": "07_ar_kalila_wa_dimna.txt",
        "negation_kind": "negation",
        "carriers": [
            "أصدر خادم الإنتاج {ip} تنبيهاً بعد أن بلغ استخدام المعالج {metric}، والفريق يتابع الأمر ضمن {cve}.",
            "ربط المهندسون ارتفاع زمن الاستجابة {metric} على المضيف {ip} بالثغرة {cve}.",
            "تم نشر تصحيح للثغرة {cve} على {ip}، مما أعاد الإنتاجية إلى ما فوق {metric}.",
        ],
        "segmentation": [
            ("أعيد تشغيل قاعدة البيانات بنجاح. لم يتم تسجيل أي أخطاء أثناء إعادة التشغيل.", 2),
            (
                "بلغت حركة المرور ذروتها في الساعة التاسعة صباحاً. وسّع الفريق العنقود. عادت زمن الاستجابة إلى طبيعتها خلال دقائق.",
                3,
            ),
            ("هل اكتملت النسخة الاحتياطية؟ لا تزال لوحة المعلومات تظهر أنها قيد التشغيل.", 2),
            ("انشر التصحيح الآن! تحقق من فحص السلامة بعد ذلك.", 2),
        ],
        "negations": [
            "لم يحدث أي فقدان للبيانات أثناء التحويل الاحتياطي.",
            "لا يمكن للخدمة إعادة التشغيل بدون ملف تكوين صالح.",
            "لم نلاحظ أبداً فقدان الحزم على ذلك الرابط.",
        ],
    },
    "bn": {
        "name": "Bengali",
        "code": "bn",
        "corpus_file": "08_bn_gitanjali.txt",
        # Same Unicode-combining-mark boundary issue as Hindi (see above) - Bengali
        # vowel signs also break a trailing \b, so use BOUND_NEGATION_RE's kind.
        "negation_kind": "bound_negation",
        "carriers": [
            "উৎপাদন সার্ভার {ip} -এ CPU ব্যবহার {metric} -এ পৌঁছানোর পর সতর্কতা জারি হয়েছে, দল এটি {cve} -এর অধীনে ট্র্যাক করছে।",
            "প্রকৌশলীরা হোস্ট {ip} -এ {metric} বিলম্বতা বৃদ্ধিকে দুর্বলতা {cve} -এর সঙ্গে যুক্ত করেছেন।",
            "{cve} -এর জন্য একটি প্যাচ {ip} -এ স্থাপন করা হয়েছে, থ্রুপুট {metric} -এর উপরে পুনরুদ্ধার হয়েছে।",
        ],
        "segmentation": [
            ("ডাটাবেস সফলভাবে পুনরায় চালু হয়েছে। পুনরায় চালুর সময় কোনো ত্রুটি রেকর্ড হয়নি।", 2),
            (
                "সকাল নয়টায় ট্রাফিক শীর্ষে পৌঁছেছিল। দল ক্লাস্টার বড় করেছে। কয়েক মিনিটের মধ্যে বিলম্বতা স্বাভাবিক হয়ে গেছে।",
                3,
            ),
            ("ব্যাকআপ কি সম্পূর্ণ হয়েছে? ড্যাশবোর্ড এখনও দেখাচ্ছে এটি চলছে।", 2),
            ("এখনই প্যাচ স্থাপন করুন! এরপর স্বাস্থ্য পরীক্ষা যাচাই করুন।", 2),
        ],
        "negations": [
            "উপযুক্ত অনুমোদন বিনা কোনো পরিবর্তন প্রয়োগ করা হয় না।",
            "বৈধ কনফিগারেশন ফাইল বিনা পরিষেবা পুনরায় চালু হয় না।",
            "পর্যাপ্ত পরীক্ষা বিনা কোনো প্যাচ স্থাপন করা হয় না।",
        ],
    },
    "pt": {
        "name": "Portuguese",
        "code": "pt",
        "corpus_file": "09_pt_dom_casmurro.txt",
        "negation_kind": "negation",
        "carriers": [
            "O servidor de produção {ip} emitiu um alerta após o uso de CPU atingir {metric}, e a equipe está rastreando isso sob {cve}.",
            "Os engenheiros associaram o pico de latência de {metric} no host {ip} à vulnerabilidade {cve}.",
            "Um patch para {cve} foi implantado em {ip}, restaurando a taxa de transferência acima de {metric}.",
        ],
        "segmentation": [
            (
                "O banco de dados reiniciou corretamente. Nenhum erro foi registrado durante a reinicialização.",
                2,
            ),
            (
                "O tráfego atingiu o pico às nove da manhã. A equipe escalou o cluster. A latência voltou ao normal em minutos.",
                3,
            ),
            ("O backup foi concluído? O painel ainda mostra que está em execução.", 2),
            ("Implante o patch agora! Verifique a checagem de integridade depois.", 2),
        ],
        "negations": [
            "Nenhuma perda de dados ocorreu durante o failover.",
            "O serviço não pode reiniciar sem um arquivo de configuração válido.",
            "Nunca observamos perda de pacotes nesse link.",
        ],
    },
    "ru": {
        "name": "Russian",
        "code": "ru",
        "corpus_file": "10_ru_rachinsky_arithmetic.txt",
        "negation_kind": "negation",
        "carriers": [
            "Производственный сервер {ip} выдал предупреждение после того, как загрузка процессора достигла {metric}, и команда отслеживает это под {cve}.",
            "Инженеры связали всплеск задержки {metric} на хосте {ip} с уязвимостью {cve}.",
            "Патч для {cve} был развёрнут на {ip}, восстановив пропускную способность выше {metric}.",
        ],
        "segmentation": [
            (
                "База данных перезапустилась без сбоев. Во время перезапуска ошибок не зафиксировано.",
                2,
            ),
            (
                "Трафик достиг пика в девять утра. Команда расширила кластер. Задержка вернулась к норме за несколько минут.",
                3,
            ),
            ("Резервное копирование завершено? Панель всё ещё показывает, что оно выполняется.", 2),
            ("Разверните патч сейчас! Затем проверьте проверку работоспособности.", 2),
        ],
        "negations": [
            "Во время отказоустойчивого переключения потери данных не произошло.",
            "Служба не может перезапуститься без действительного файла конфигурации.",
            "На этой линии мы никогда не наблюдали потери пакетов.",
        ],
    },
    "ja": {
        "name": "Japanese",
        "code": "ja",
        "corpus_file": "11_ja_akutagawa_rashomon.txt",
        "negation_kind": None,  # ...ない inflection isn't covered by the negation-word regexes
        "carriers": [
            "本番サーバー {ip} はCPU使用率が {metric} に達した後にアラートを発し、チームは {cve} のもとで追跡しています。",
            "エンジニアはホスト {ip} での {metric} のレイテンシ急増を脆弱性 {cve} に関連付けました。",
            "{cve} に対するパッチが {ip} に展開され、スループットが {metric} 以上に回復しました。",
        ],
        "segmentation": [
            ("データベースは正常に再起動しました。再起動中にエラーは記録されませんでした。", 2),
            (
                "トラフィックは午前九時にピークに達しました。チームはクラスターを拡張しました。数分でレイテンシは正常に戻りました。",
                3,
            ),
            ("バックアップは完了しましたか？ダッシュボードにはまだ実行中と表示されています。", 2),
            ("今すぐパッチを展開してください！その後、ヘルスチェックを確認してください。", 2),
        ],
        "negations": [
            "フェイルオーバー中にデータ損失は発生しませんでした。",
            "有効な設定ファイルなしではサービスを再起動できません。",
            "そのリンクでパケット損失を確認したことは一度もありません。",
        ],
    },
    "he": {
        "name": "Hebrew",
        "code": "he",
        "corpus_file": "12_he_bereshit_genesis.txt",
        "negation_kind": "negation",
        "carriers": [
            "שרת הייצור {ip} הפעיל התראה לאחר שניצול המעבד הגיע ל- {metric}, והצוות עוקב אחר כך תחת {cve}.",
            "המהנדסים קישרו את קפיצת זמן ההשהיה של {metric} במארח {ip} לפגיעות {cve}.",
            "תיקון עבור {cve} הופעל בשרת {ip}, והשיב את התפוקה מעל {metric}.",
        ],
        "segmentation": [
            ("מסד הנתונים הופעל מחדש בהצלחה. לא נרשמו שגיאות במהלך ההפעלה מחדש.", 2),
            (
                "התנועה הגיעה לשיא בתשע בבוקר. הצוות הרחיב את האשכול. זמן ההשהיה חזר לקדמותו תוך דקות.",
                3,
            ),
            ("האם הגיבוי הושלם? הלוח עדיין מציג שהוא פועל.", 2),
            ("הפעל את התיקון עכשיו! אמת את בדיקת התקינות לאחר מכן.", 2),
        ],
        "negations": [
            "לא אירע אובדן נתונים במהלך המעבר לגיבוי.",
            "לא ניתן להפעיל מחדש את השירות ללא קובץ תצורה תקין.",
            "מעולם לא צפינו באובדן חבילות בקישור הזה.",
        ],
    },
}

# (ip, cve, metric) substitutions cycled across the 3 carrier templates to build
# 6 distinct atom-extraction cases per language without repeating any sentence.
ATOM_SUBSTITUTIONS = [
    ("10.0.4.12", "CVE-2026-10432", "45 ms"),
    ("10.0.9.31", "CVE-2026-20981", "120 ms"),
    ("10.1.2.44", "CVE-2026-31207", "78 ms"),
    ("10.1.7.19", "CVE-2026-40556", "212 ms"),
    ("10.2.5.63", "CVE-2026-50871", "33 ms"),
    ("10.2.8.27", "CVE-2026-61190", "156 ms"),
]

SLICE_CHARS = 6000


def build_atom_cases(cfg: dict) -> list[tuple[str, str, str, str]]:
    cases = []
    for i, (ip, cve, metric) in enumerate(ATOM_SUBSTITUTIONS):
        template = cfg["carriers"][i % len(cfg["carriers"])]
        text = template.format(ip=ip, cve=cve, metric=metric)
        cases.append((text, cve, ip, metric))
    return cases


def generate_test_file(idx: int, cfg: dict) -> None:
    code = cfg["code"]
    upper = code.upper()
    filename = f"test_lang_{idx:02d}_{code}.py"
    target = TESTS_DIR / filename

    atom_cases = build_atom_cases(cfg)
    span_cases = [c[0] for c in atom_cases[:3]]

    lines: list[str] = []
    lines.append(f'"""Honest multilingual test suite for {cfg["name"]} ({code}).')
    lines.append("")
    lines.append("Real, hand-authored native-language sentences (not templated placeholders")
    lines.append("or English carrier text with a foreign word pasted in). See")
    lines.append("scripts/generate_multilingual_tests.py for how this file is generated and why.")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from pathlib import Path")
    lines.append("")
    lines.append("import pytest")
    lines.append("")
    lines.append("from contextcull.api import ContextCompiler")
    lines.append("from contextcull.detect.atoms import extract_atoms")
    lines.append("from contextcull.ingest.decoder import clean_char_to_byte_span, ingest_bytes")
    lines.append("from contextcull.ir.models import CompileMode, CompilePolicy")
    lines.append("from contextcull.segment.sentence import segment_sentences")
    lines.append("")
    lines.append("REPO_ROOT = Path(__file__).resolve().parents[2]")
    lines.append(f'CORPUS_FILE = REPO_ROOT / "{CORPUS_DIR}" / "{cfg["corpus_file"]}"')
    lines.append("")
    lines.append("")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# 1. Native sentence segmentation")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")
    lines.append(f"SEGMENTATION_CASES_{upper} = [")
    for text, count in cfg["segmentation"]:
        lines.append(f"    ({text!r}, {count}),")
    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append(f'@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_{upper})')
    lines.append(f"def test_{code}_sentence_segmentation(text: str, expected_count: int):")
    lines.append("    spans = segment_sentences(text)")
    lines.append("    assert len(spans) == expected_count")
    lines.append("    for s in spans:")
    lines.append('        assert s.text.strip() != ""')
    lines.append("        assert s.end_char > s.start_char")
    lines.append("")
    lines.append("")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# 2. Atom extraction: CVE, IPv4 AND metric must all be detected")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")
    lines.append(f"ATOM_CASES_{upper} = [")
    for text, cve, ip, metric in atom_cases:
        lines.append(f"    ({text!r}, {cve!r}, {ip!r}, {metric!r}),")
    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append(
        f'@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_metric", ATOM_CASES_{upper})'
    )
    lines.append(
        f"def test_{code}_technical_atoms(text: str, expected_cve: str, expected_ip: str, expected_metric: str):"
    )
    lines.append("    ingest = ingest_bytes(text.encode('utf-8'))")
    lines.append("    atoms = extract_atoms(ingest)")
    lines.append("    surfaces = [a.surface for a in atoms]")
    lines.append(
        '    assert any(expected_cve in s for s in surfaces), f"Missing CVE {expected_cve} in {surfaces}"'
    )
    lines.append(
        '    assert any(expected_ip in s for s in surfaces), f"Missing IP {expected_ip} in {surfaces}"'
    )
    lines.append(
        "    assert any(expected_metric.split()[0] in s for s in surfaces), "
        'f"Missing metric {expected_metric} in {surfaces}"'
    )
    lines.append("")
    lines.append("")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# 3. Negation detection")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")
    lines.append(f"NEGATION_CASES_{upper} = [")
    for text in cfg["negations"]:
        lines.append(f"    {text!r},")
    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append(f'@pytest.mark.parametrize("text", NEGATION_CASES_{upper})')
    lines.append(f"def test_{code}_negation_detection(text: str):")
    if cfg["negation_kind"] is not None:
        expected_kind = cfg["negation_kind"]
        lines.append("    ingest = ingest_bytes(text.encode('utf-8'))")
        lines.append("    atoms = extract_atoms(ingest)")
        lines.append(
            '    kinds = [a.kind for a in atoms if a.kind in ("negation", "bound_negation")]'
        )
        lines.append(f"    assert {expected_kind!r} in kinds, (")
        lines.append(
            f'        f"Expected a {expected_kind!r} atom, got kinds={{kinds}} for {{text!r}}"'
        )
        lines.append("    )")
    else:
        lines.append("    # Japanese negation is the grammatical ...ない inflection, which neither")
        lines.append(
            "    # the Western/Hebrew/Other word-list regex nor the CJK prefix-negation regex"
        )
        lines.append(
            "    # covers - so this asserts the extractive guarantee instead: compiling at"
        )
        lines.append("    # COMPACT mode must not corrupt or drop the negation clause.")
        lines.append("    compiler = ContextCompiler(mode=CompileMode.COMPACT)")
        lines.append(
            "    result = compiler.compile(text.encode('utf-8'), policy=CompilePolicy(mode=CompileMode.COMPACT))"
        )
        lines.append("    assert result.status == 'OK'")
        lines.append("    assert text in result.text")
    lines.append("")
    lines.append("")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# 4. Byte-exact UTF-8 SourceMap span round-trip")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")
    lines.append(f"SPAN_CASES_{upper} = [")
    for text in span_cases:
        lines.append(f"    {text!r},")
    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append(f'@pytest.mark.parametrize("text", SPAN_CASES_{upper})')
    lines.append(f"def test_{code}_utf8_byte_span_roundtrip(text: str):")
    lines.append("    raw_bytes = text.encode('utf-8')")
    lines.append("    ingest = ingest_bytes(raw_bytes)")
    lines.append("    assert len(ingest.source_map.raw_bytes) == len(raw_bytes)")
    lines.append("    for char_idx in (0, len(text) // 3, len(text) // 2, len(text) - 1):")
    lines.append("        span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)")
    lines.append(
        "        assert raw_bytes[span.start : span.end].decode('utf-8') == ingest.clean_text[char_idx]"
    )
    lines.append("")
    lines.append("")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# 5. End-to-end compile on a slice of the real corpus")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")
    lines.append(f"def test_{code}_end_to_end_real_corpus_slice():")
    lines.append("    if not CORPUS_FILE.exists():")
    lines.append('        pytest.skip(f"corpus file not present: {CORPUS_FILE}")')
    lines.append(f"    raw_text = CORPUS_FILE.read_text(encoding='utf-8')[:{SLICE_CHARS}]")
    lines.append("    raw_bytes = raw_text.encode('utf-8')")
    lines.append("    compiler = ContextCompiler(mode=CompileMode.COMPACT)")
    lines.append(
        "    result = compiler.compile(raw_bytes, policy=CompilePolicy(mode=CompileMode.COMPACT))"
    )
    lines.append("    assert result.status == 'OK', result.diagnostics")
    lines.append("    assert 0 < len(result.text) < len(raw_text)")
    lines.append("")
    lines.append("    ingest = ingest_bytes(raw_bytes)")
    lines.append(
        "    for char_idx in (0, len(raw_text) // 3, len(raw_text) // 2, len(raw_text) - 1):"
    )
    lines.append("        span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)")
    lines.append(
        "        assert raw_bytes[span.start : span.end].decode('utf-8') == ingest.clean_text[char_idx]"
    )
    lines.append("")

    target.write_text("\n".join(lines), encoding="utf-8")
    n_cases = (
        len(cfg["segmentation"]) + len(atom_cases) + len(cfg["negations"]) + len(span_cases) + 1
    )
    print(f"Wrote {target.name} ({n_cases} cases)")


def main() -> None:
    print("=== Generating honest multilingual test suite ===")
    for idx, (_, cfg) in enumerate(LANG_CONFIGS.items(), 1):
        generate_test_file(idx, cfg)
    print(f"Done: {len(LANG_CONFIGS)} language files in tests/multilingual/.")


if __name__ == "__main__":
    main()
