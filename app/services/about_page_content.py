from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class AboutContent:
    seo_title: str
    meta_description: str
    h1: str
    intro: str
    why_title: str
    why_body: str
    what_title: str
    what_body: str
    who_title: str
    who_body: str
    how_title: str
    how_body: str
    does_title: str
    does_items: List[str]
    doesnt_title: str
    doesnt_items: List[str]
    conclusion_title: str
    conclusion_body: str
    hero_kicker: str
    hero_support: str
    leader_eyebrow: str
    photo_caption: str
    image_alt: str
    locale: str
    dir: str = "ltr"
    html_lang: str = "fr"


ABOUT_CONTENT: Dict[str, AboutContent] = {
    "fr": AboutContent(
        seo_title="Qui est Israel Growth Venture | Cabinet d’implantation et d’accompagnement commercial en Israël",
        meta_description="Israel Growth Venture est un cabinet indépendant spécialisé dans l’implantation, le développement commercial, la recherche active d’opportunités immobilières commerciales et l’accompagnement opérationnel en Israël.",
        h1="Qui est Israel Growth Venture",
        intro="Israel Growth Venture est un cabinet indépendant spécialisé dans l’implantation, le développement commercial, la recherche active d’opportunités immobilières commerciales et l’accompagnement opérationnel en Israël pour des enseignes et entreprises étrangères.",
        why_title="Pourquoi IGV existe",
        why_body="Israel Growth Venture est né d’un constat simple : beaucoup d’entreprises regardent Israël comme un marché d’opportunité, mais peu disposent d’un relais local capable de lire le terrain, les zones, les réalités commerciales, les contraintes d’implantation et les étapes concrètes d’une entrée sur le marché. Au-delà de la stratégie, de nombreux projets échouent aussi par manque de lecture locale sur les emplacements, les conditions locatives et la compréhension des engagements contractuels.",
        what_title="Ce que fait IGV",
        what_body="IGV accompagne principalement des marques et entreprises étrangères qui souhaitent évaluer leur potentiel en Israël, structurer leur stratégie d’entrée, comprendre les formats possibles de développement et identifier des opportunités cohérentes avec leur activité. L’intervention peut inclure l’analyse de marché, l’audit d’implantation, l’étude du bon format de développement (popup, succursales, franchise, flagship), le ciblage de villes ou zones prioritaires, la recherche active d’emplacements commerciaux, les premiers échanges liés aux conditions d’implantation et la mise en relation avec des partenaires utiles au projet.",
        who_title="Qui dirige IGV",
        who_body="Israel Growth Venture est dirigé par Mickaël Benmoussa. Son parcours s’est construit autour du commerce, du terrain et de l’immobilier commercial. Son approche repose sur une logique simple : avant de vouloir ouvrir en Israël, il faut comprendre le marché, le format adapté, la zone, le niveau de risque, les conditions réelles d’exécution et la réalité des engagements à prendre.",
        how_title="La manière de travailler",
        how_body="IGV travaille en amont des décisions d’ouverture, mais peut également accompagner la phase terrain lorsque le projet le justifie. Cela peut inclure la recherche active d’opportunités en immobilier commercial, l’identification d’emplacements cohérents, l’appui dans les échanges et négociations préalables, ainsi que l’accompagnement à la compréhension et à la traduction des contrats dans la langue maternelle du client, sans se substituer à la validation juridique finale par un professionnel compétent.",
        does_title="Ce que IGV fait",
        does_items=[
            "Audit d’implantation en Israël",
            "Analyse de marché et de faisabilité",
            "Réflexion stratégique sur le bon format d’entrée",
            "Étude du bon format de développement (popup, succursales, franchise, flagship)",
            "Ciblage de villes, zones et opportunités commerciales",
            "Recherche active de locaux et d’opportunités en immobilier commercial",
            "Accompagnement dans les premiers échanges et négociations liés aux baux",
            "Aide à la compréhension et à la traduction des contrats dans la langue du client",
            "Mise en relation avec des partenaires locaux selon les besoins du projet",
        ],
        doesnt_title="Ce que IGV ne fait pas",
        doesnt_items=[
            "IGV n’est pas un fonds d’investissement",
            "IGV n’est pas un cabinet comptable",
            "IGV ne remplace pas un avocat local",
            "IGV ne valide pas juridiquement un contrat à la place d’un professionnel habilité",
            "IGV intervient comme cabinet stratégique et opérationnel d’implantation et d’accompagnement terrain",
        ],
        conclusion_title="Conclusion",
        conclusion_body="IGV s’adresse aux entreprises qui veulent aborder Israël avec une lecture sérieuse, locale, structurée et concrète, avant et pendant les premières étapes d’une ouverture, d’une franchise, d’une succursale ou d’un développement commercial.",
        hero_kicker="Cabinet indépendant en Israël",
        hero_support="Implantation, développement commercial, immobilier commercial et accompagnement terrain.",
        leader_eyebrow="Qui dirige IGV",
        photo_caption="Mickaël Benmoussa",
        image_alt="Portrait de Mickaël Benmoussa",
        locale="fr_FR",
        html_lang="fr",
    ),
    "en": AboutContent(
        seo_title="Who is Israel Growth Venture | Market Entry and Commercial Expansion Firm in Israel",
        meta_description="Israel Growth Venture is an independent firm specialized in market entry, business expansion, active sourcing of commercial real-estate opportunities, and operational support in Israel for foreign brands and companies.",
        h1="Who is Israel Growth Venture",
        intro="Israel Growth Venture is an independent firm specialized in market entry, business expansion, active sourcing of commercial real-estate opportunities, and operational support in Israel for foreign brands and companies.",
        why_title="Why IGV exists",
        why_body="Israel Growth Venture was created from a simple observation: many companies see Israel as a market of opportunity, but very few have a local partner able to read the field, understand the zones, the commercial realities, the constraints of market entry, and the concrete steps required for a real launch. Beyond strategy, many projects also fail because they lack local understanding of locations, lease conditions, and contractual commitments.",
        what_title="What IGV does",
        what_body="IGV mainly supports foreign brands and companies that want to assess their potential in Israel, structure their entry strategy, understand the possible development formats, and identify opportunities consistent with their business. This may include market analysis, market-entry audits, the study of the right development format (popup, branch, franchise, flagship), city and area targeting, active sourcing of commercial locations, early discussions regarding location conditions, and introductions to relevant local partners.",
        who_title="Who leads IGV",
        who_body="Israel Growth Venture is led by Mickaël Benmoussa. His background is rooted in business, field analysis, and commercial real estate. His approach is based on a simple logic: before opening in Israel, a company must understand the market, the right format, the right area, the level of risk, the real execution conditions, and the nature of the commitments involved.",
        how_title="How IGV works",
        how_body="IGV works upstream, before opening decisions are made, but can also support the field phase when the project requires it. This may include active sourcing of commercial real-estate opportunities, identification of relevant locations, support in early exchanges and lease negotiations, and assistance in understanding and translating contracts into the client’s native language, without replacing final legal validation by a qualified professional.",
        does_title="What IGV does",
        does_items=[
            "Israel market-entry audits",
            "Market and feasibility analysis",
            "Strategic review of the right entry format",
            "Study of the right development format (popup, branch, franchise, flagship)",
            "Targeting of cities, areas, and commercial opportunities",
            "Active sourcing of commercial locations and real-estate opportunities",
            "Support in early lease-related discussions and negotiations",
            "Assistance in understanding and translating contracts into the client’s language",
            "Introductions to local partners depending on project needs",
        ],
        doesnt_title="What IGV does not do",
        doesnt_items=[
            "IGV is not an investment fund",
            "IGV is not an accounting firm",
            "IGV does not replace a local lawyer",
            "IGV does not provide final legal validation of contracts in place of a qualified professional",
            "IGV acts as a strategic and operational market-entry and field-support firm",
        ],
        conclusion_title="Conclusion",
        conclusion_body="IGV works with companies that want to approach Israel in a serious, local, structured, and concrete way, before and during the early stages of an opening, a franchise, a branch, or a commercial development project.",
        hero_kicker="Independent firm in Israel",
        hero_support="Market entry, business expansion, commercial real estate and field support.",
        leader_eyebrow="Who leads IGV",
        photo_caption="Mickaël Benmoussa",
        image_alt="Portrait of Mickaël Benmoussa",
        locale="en_US",
        html_lang="en",
    ),
    "he": AboutContent(
        seo_title="מי היא Israel Growth Venture | משרד לכניסה לשוק ולהתרחבות מסחרית בישראל",
        meta_description="Israel Growth Venture היא חברה עצמאית המתמחה בכניסה לשוק, בפיתוח עסקי, באיתור פעיל של הזדמנויות בנדל״ן מסחרי ובליווי תפעולי בישראל עבור מותגים וחברות זרות.",
        h1="מי היא Israel Growth Venture",
        intro="Israel Growth Venture היא חברה עצמאית המתמחה בכניסה לשוק, בפיתוח עסקי, באיתור פעיל של הזדמנויות בנדל״ן מסחרי ובליווי תפעולי בישראל עבור מותגים וחברות זרות.",
        why_title="למה IGV קיימת",
        why_body="Israel Growth Venture נולדה מתוך מציאות פשוטה: חברות רבות רואות בישראל שוק עם פוטנציאל, אך מעטות מחזיקות בשותף מקומי שמסוגל להבין את השטח, את האזורים, את המציאות המסחרית, את מגבלות הכניסה לשוק ואת השלבים המעשיים של הקמה אמיתית. מעבר לאסטרטגיה, פרויקטים רבים נכשלים גם בגלל חוסר הבנה מקומית של מיקומים, תנאי שכירות ומשמעויות חוזיות.",
        what_title="מה IGV עושה",
        what_body="IGV מלווה בעיקר מותגים וחברות זרות המעוניינים לבדוק את הפוטנציאל שלהם בישראל, לבנות אסטרטגיית כניסה, להבין את מודלי הפיתוח האפשריים ולאתר הזדמנויות המתאימות לפעילותם. הליווי יכול לכלול ניתוח שוק, בדיקת היתכנות לכניסה, בחינת מודל הפיתוח הנכון (פופ-אפ, סניף, זכיינות, חנות דגל), מיקוד ערים ואזורים מועדפים, איתור פעיל של מיקומים מסחריים, שיחות ראשוניות לגבי תנאי הקמה וחיבור לשותפים מקומיים רלוונטיים.",
        who_title="מי עומד מאחורי IGV",
        who_body="בראש Israel Growth Venture עומד Mickaël Benmoussa. הרקע שלו בנוי סביב עולם המסחר, העבודה בשטח והנדל״ן המסחרי. הגישה שלו פשוטה: לפני שפותחים בישראל, צריך להבין את השוק, את המודל המתאים, את האזור הנכון, את רמת הסיכון, את תנאי הביצוע האמיתיים ואת ההתחייבויות שהפרויקט דורש.",
        how_title="איך IGV עובדת",
        how_body="IGV פועלת בשלב שלפני ההחלטות על פתיחה, אך יכולה גם ללוות את שלב העבודה בשטח כאשר הפרויקט מצריך זאת. הדבר יכול לכלול איתור פעיל של הזדמנויות בנדל״ן מסחרי, זיהוי מיקומים רלוונטיים, סיוע בשיחות ובמשא ומתן ראשוני על תנאי שכירות, וכן ליווי בהבנה ובתרגום של חוזים לשפת האם של הלקוח, מבלי להחליף אישור משפטי סופי של איש מקצוע מוסמך.",
        does_title="מה IGV עושה",
        does_items=[
            "בדיקות היתכנות לכניסה לשוק בישראל",
            "ניתוח שוק ובדיקת התאמה",
            "בחינה אסטרטגית של מודל הכניסה הנכון",
            "בחינת מודל הפיתוח הנכון (פופ-אפ, סניף, זכיינות, חנות דגל)",
            "מיקוד ערים, אזורים והזדמנויות מסחריות",
            "איתור פעיל של נכסים והזדמנויות בנדל״ן מסחרי",
            "סיוע בשיחות ובמשא ומתן ראשוני בנוגע לתנאי שכירות",
            "סיוע בהבנה ובתרגום של חוזים לשפת הלקוח",
            "חיבור לשותפים מקומיים לפי צורכי הפרויקט",
        ],
        doesnt_title="מה IGV לא עושה",
        doesnt_items=[
            "IGV אינה קרן השקעות",
            "IGV אינה משרד רואי חשבון",
            "IGV אינה מחליפה עורך דין מקומי",
            "IGV אינה מעניקה אישור משפטי סופי לחוזים במקום איש מקצוע מוסמך",
            "IGV פועלת כמשרד אסטרטגי ותפעולי לכניסה לשוק ולליווי בשטח",
        ],
        conclusion_title="סיכום",
        conclusion_body="IGV מיועדת לחברות שרוצות לגשת לישראל בצורה רצינית, מקומית, מסודרת ומעשית, לפני ובמהלך השלבים הראשונים של פתיחה, זכיינות, סניף או פיתוח מסחרי.",
        hero_kicker="חברה עצמאית בישראל",
        hero_support="כניסה לשוק, פיתוח עסקי, נדל״ן מסחרי וליווי בשטח.",
        leader_eyebrow="מי עומד מאחורי IGV",
        photo_caption="Mickaël Benmoussa",
        image_alt="תמונה של Mickaël Benmoussa",
        locale="he_IL",
        dir="rtl",
        html_lang="he",
    ),
}


IMG_SRC_PATTERN = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)


def extract_primary_image_src(existing_html: Optional[str]) -> Optional[str]:
    if not existing_html:
        return None
    match = IMG_SRC_PATTERN.search(existing_html)
    return match.group(1).strip() if match else None


def build_about_page_document(language: str, existing_html: Optional[str] = None) -> Dict[str, object]:
    content = ABOUT_CONTENT[language]
    image_src = extract_primary_image_src(existing_html)

    hero_media = ""
    if image_src:
        hero_media = f"""
          <figure class="igv-about__portrait-frame">
            <img class="igv-about__portrait" src="{image_src}" alt="{content.image_alt}" loading="eager" />
            <figcaption class="igv-about__portrait-caption">{content.photo_caption}</figcaption>
          </figure>
        """
    else:
        hero_media = f"""
          <div class="igv-about__portrait-frame igv-about__portrait-frame--placeholder" aria-label="{content.image_alt}">
            <div class="igv-about__portrait-placeholder">IGV</div>
            <div class="igv-about__portrait-caption">{content.photo_caption}</div>
          </div>
        """

    html = f"""
<section class="igv-about igv-about--{language}" lang="{content.html_lang}" dir="{content.dir}" data-page="about" data-lang="{language}">
  <style>
    .igv-about {{
      --igv-ink: #102033;
      --igv-muted: #5b6776;
      --igv-line: rgba(16, 32, 51, 0.12);
      --igv-paper: #f6f1e8;
      --igv-surface: #fffdf9;
      --igv-accent: #c48a3a;
      --igv-accent-soft: rgba(196, 138, 58, 0.14);
      --igv-shadow: 0 24px 60px rgba(16, 32, 51, 0.12);
      font-family: "Georgia", "Times New Roman", serif;
      color: var(--igv-ink);
      background:
        radial-gradient(circle at top left, rgba(196, 138, 58, 0.14), transparent 34%),
        linear-gradient(180deg, #f7f3eb 0%, #ffffff 24%, #fbfaf7 100%);
      padding: 48px 20px 72px;
    }}
    .igv-about *, .igv-about *::before, .igv-about *::after {{ box-sizing: border-box; }}
    .igv-about__shell {{ max-width: 1180px; margin: 0 auto; display: grid; gap: 28px; }}
    .igv-about__hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
      gap: 28px;
      align-items: stretch;
    }}
    .igv-about__panel {{
      background: rgba(255, 253, 249, 0.92);
      border: 1px solid var(--igv-line);
      border-radius: 28px;
      box-shadow: var(--igv-shadow);
      overflow: hidden;
    }}
    .igv-about__hero-copy {{
      padding: 40px;
      display: grid;
      gap: 18px;
      align-content: start;
      min-height: 100%;
    }}
    .igv-about__kicker {{
      display: inline-flex;
      width: fit-content;
      align-items: center;
      gap: 10px;
      font-family: Arial, sans-serif;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--igv-muted);
      padding: 10px 14px;
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--igv-line);
      border-radius: 999px;
    }}
    .igv-about h1, .igv-about h2, .igv-about h3, .igv-about p, .igv-about ul {{ margin: 0; }}
    .igv-about h1 {{
      font-size: clamp(2.4rem, 5vw, 4.4rem);
      line-height: 0.95;
      letter-spacing: -0.04em;
    }}
    .igv-about__intro {{
      font-size: clamp(1.02rem, 1.5vw, 1.22rem);
      line-height: 1.75;
      color: #213346;
      max-width: 58ch;
    }}
    .igv-about__support {{
      display: grid;
      gap: 10px;
      padding-top: 12px;
      border-top: 1px solid var(--igv-line);
      font-family: Arial, sans-serif;
      font-size: 0.98rem;
      color: var(--igv-muted);
    }}
    .igv-about__hero-media {{
      position: relative;
      min-height: 100%;
      padding: 22px;
      background:
        linear-gradient(180deg, rgba(196, 138, 58, 0.18), rgba(16, 32, 51, 0.04)),
        linear-gradient(135deg, #efe4d1 0%, #fcfaf6 100%);
      display: grid;
      align-items: center;
    }}
    .igv-about__portrait-frame {{
      position: relative;
      min-height: 100%;
      background: #efe7db;
      border-radius: 24px;
      overflow: hidden;
      box-shadow: 0 24px 40px rgba(16, 32, 51, 0.18);
      display: grid;
      align-content: end;
    }}
    .igv-about__portrait {{
      display: block;
      width: 100%;
      height: 100%;
      min-height: 460px;
      object-fit: cover;
      object-position: center top;
      background: #e9dece;
    }}
    .igv-about__portrait-frame--placeholder {{
      padding: 28px;
      border: 1px dashed rgba(16, 32, 51, 0.2);
      align-items: end;
      justify-items: start;
    }}
    .igv-about__portrait-placeholder {{
      width: 100%;
      min-height: 460px;
      display: grid;
      place-items: center;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(196, 138, 58, 0.18), rgba(16, 32, 51, 0.1));
      color: var(--igv-ink);
      font-size: clamp(2rem, 10vw, 4rem);
      letter-spacing: 0.2em;
    }}
    .igv-about__portrait-caption {{
      position: absolute;
      left: 20px;
      right: 20px;
      bottom: 20px;
      padding: 14px 16px;
      background: rgba(255, 253, 249, 0.9);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(16, 32, 51, 0.08);
      border-radius: 18px;
      font-family: Arial, sans-serif;
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--igv-ink);
    }}
    .igv-about__grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 24px;
    }}
    .igv-about__section {{
      padding: 30px;
      display: grid;
      gap: 16px;
    }}
    .igv-about__section h2 {{
      font-size: clamp(1.5rem, 2vw, 2.1rem);
      line-height: 1.05;
      letter-spacing: -0.03em;
    }}
    .igv-about__section p {{
      font-family: Arial, sans-serif;
      font-size: 1rem;
      line-height: 1.8;
      color: #2a3b4a;
    }}
    .igv-about__eyebrow {{
      font-family: Arial, sans-serif;
      font-size: 0.8rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--igv-accent);
      font-weight: 700;
    }}
    .igv-about__lists {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 24px;
    }}
    .igv-about__list {{
      padding: 30px;
      display: grid;
      gap: 16px;
      align-content: start;
    }}
    .igv-about__list--positive {{
      background: linear-gradient(180deg, rgba(255, 253, 249, 0.98), rgba(247, 243, 235, 0.92));
    }}
    .igv-about__list--negative {{
      background: linear-gradient(180deg, rgba(255, 251, 247, 0.98), rgba(246, 239, 232, 0.92));
    }}
    .igv-about__list ul {{
      list-style: none;
      padding: 0;
      display: grid;
      gap: 12px;
    }}
    .igv-about__list li {{
      position: relative;
      padding-inline-start: 22px;
      font-family: Arial, sans-serif;
      line-height: 1.65;
      color: #2a3b4a;
    }}
    .igv-about__list li::before {{
      content: "";
      position: absolute;
      inset-inline-start: 0;
      top: 0.72em;
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--igv-accent);
      transform: translateY(-50%);
    }}
    .igv-about__conclusion {{
      padding: 34px;
      background:
        linear-gradient(135deg, rgba(16, 32, 51, 0.98), rgba(33, 51, 70, 0.92)),
        linear-gradient(135deg, rgba(196, 138, 58, 0.12), transparent);
      color: #f7f3eb;
      display: grid;
      gap: 14px;
    }}
    .igv-about__conclusion h2, .igv-about__conclusion p {{ color: inherit; }}
    .igv-about__conclusion p {{
      font-family: Arial, sans-serif;
      line-height: 1.8;
      max-width: 76ch;
    }}
    .igv-about--he {{ font-family: "Noto Sans Hebrew", Arial, sans-serif; }}
    .igv-about--he h1, .igv-about--he h2, .igv-about--he h3 {{ font-family: "Noto Sans Hebrew", Arial, sans-serif; }}
    @media (max-width: 960px) {{
      .igv-about__hero, .igv-about__grid, .igv-about__lists {{ grid-template-columns: 1fr; }}
      .igv-about__hero-copy, .igv-about__section, .igv-about__list, .igv-about__conclusion {{ padding: 24px; }}
      .igv-about__portrait, .igv-about__portrait-placeholder {{ min-height: 360px; }}
    }}
    @media (max-width: 640px) {{
      .igv-about {{ padding: 28px 14px 52px; }}
      .igv-about__hero-copy {{ gap: 14px; }}
      .igv-about__kicker {{ letter-spacing: 0.12em; }}
      .igv-about__intro, .igv-about__section p, .igv-about__list li, .igv-about__conclusion p {{ font-size: 0.98rem; }}
    }}
  </style>
  <div class="igv-about__shell">
    <section class="igv-about__hero">
      <div class="igv-about__panel igv-about__hero-copy">
        <div class="igv-about__kicker">{content.hero_kicker}</div>
        <h1>{content.h1}</h1>
        <p class="igv-about__intro">{content.intro}</p>
        <div class="igv-about__support">
          <strong>{content.hero_support}</strong>
          <span>{content.how_body}</span>
        </div>
      </div>
      <div class="igv-about__panel igv-about__hero-media">
        {hero_media}
      </div>
    </section>

    <section class="igv-about__grid">
      <article class="igv-about__panel igv-about__section">
        <h2>{content.why_title}</h2>
        <p>{content.why_body}</p>
      </article>
      <article class="igv-about__panel igv-about__section">
        <h2>{content.what_title}</h2>
        <p>{content.what_body}</p>
      </article>
      <article class="igv-about__panel igv-about__section">
        <div class="igv-about__eyebrow">{content.leader_eyebrow}</div>
        <h2>{content.who_title}</h2>
        <p>{content.who_body}</p>
      </article>
      <article class="igv-about__panel igv-about__section">
        <h2>{content.how_title}</h2>
        <p>{content.how_body}</p>
      </article>
    </section>

    <section class="igv-about__lists">
      <article class="igv-about__panel igv-about__list igv-about__list--positive">
        <h2>{content.does_title}</h2>
        <ul>
          {"".join(f"<li>{item}</li>" for item in content.does_items)}
        </ul>
      </article>
      <article class="igv-about__panel igv-about__list igv-about__list--negative">
        <h2>{content.doesnt_title}</h2>
        <ul>
          {"".join(f"<li>{item}</li>" for item in content.doesnt_items)}
        </ul>
      </article>
    </section>

    <section class="igv-about__panel igv-about__conclusion">
      <h2>{content.conclusion_title}</h2>
      <p>{content.conclusion_body}</p>
    </section>
  </div>
</section>
""".strip()

    canonical_path = "/about/" if language == "fr" else f"/{language}/about/"

    return {
        "page": "about",
        "language": language,
        "content": {
            "main": {
                "title": content.h1,
                "html": html,
            },
            "seo": {
                "title": content.seo_title,
                "description": content.meta_description,
                "canonical": canonical_path,
                "robots": "index,follow",
                "h1": content.h1,
                "locale": content.locale,
            },
        },
    }
