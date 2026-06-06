"""extensions — extracted from univ_defs.py."""

from __future__ import annotations

from itertools import chain

TEXT_ENCODINGS: Final[tuple[str, ...]] = (
    "utf-8",           "latin-1",        "ascii",           "iso-8859-1",         "big5",
    "utf-8-sig",       "utf-16",         "utf-16-be",       "utf-16-le",          "utf-32",
    "utf-32-be",       "utf-32-le",      "cp1252",          "cp1251",             "cp1250",
    "cp1253",          "cp1254",         "cp1255",          "cp1256",             "cp1257",
    "cp1258",          "iso-8859-2",     "iso-8859-3",      "iso-8859-4",         "iso-8859-5",
    "iso-8859-6",      "iso-8859-7",     "iso-8859-8",      "iso-8859-9",         "iso-8859-10",
    "iso-8859-11",     "iso-8859-13",    "iso-8859-14",     "iso-8859-15",        "iso-8859-16",
    "cp437",           "cp850",          "cp852",           "cp855",              "cp857",
    "cp858",           "cp860",          "cp861",           "cp862",              "cp863",
    "cp864",           "cp865",          "cp866",           "cp869",              "cp037",
    "cp424",           "cp500",          "cp720",           "cp737",              "cp775",
    "cp874",           "cp875",          "cp932",           "cp949",              "cp950",
    "cp1006",          "cp1026",         "cp1125",          "cp1140",             "big5hkscs",
    "gb2312",          "gbk",            "gb18030",         "euc-jp",             "euc-jis-2004",
    "euc-jisx0213",    "euc-kr",         "iso2022-jp",      "iso2022-jp-1",       "iso2022-jp-2",
    "iso2022-jp-2004", "iso2022-jp-3",   "iso2022-jp-ext",  "iso2022-kr",         "johab",
    "koi8-r",          "koi8-t",         "koi8-u",          "kz1048",             "mac-cyrillic",
    "mac-greek",       "mac-iceland",    "mac-latin2",      "mac-roman",          "mac-turkish",
    "ptcp154",         "shift-jis",      "shift-jis-2004",  "shift-jisx0213",     "hz",
    "tis-620",         "utf-7",          "base64",          "bz2",                "charmap",
    "cp273",           "cp856",          "euc_jis_2004",    "euc_jisx0213",       "euc_jp",
    "euc_kr",          "hex",            "hp-roman8",       "idna",               "iso2022_jp",
    "iso2022_jp_1",    "iso2022_jp_2",   "iso2022_jp_2004", "iso2022_jp_3",       "iso2022_jp_ext",
    "iso2022_kr",      "iso8859-1",      "iso8859-10",      "iso8859-11",         "iso8859-13",
    "iso8859-14",      "iso8859-15",     "iso8859-16",      "iso8859-2",          "iso8859-3",
    "iso8859-4",       "iso8859-5",      "iso8859-6",       "iso8859-7",          "iso8859-8",
    "iso8859-9",       "mac-arabic",     "mac-croatian",    "mac-farsi",          "mac-romanian",
    "palmos",          "punycode",       "quopri",          "raw-unicode-escape", "rot-13",
    "shift_jis",       "shift_jis_2004", "shift_jisx0213",  "unicode-escape",     "uu",
    "zlib",
)

TEXT_ENCODINGS_SET: Final[frozenset[str]] = frozenset(TEXT_ENCODINGS)  # sets are faster

PYTHON_EXTENSIONS:    Final[tuple[str, ...]] = (".py", ".pyw")

PYTHON_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(PYTHON_EXTENSIONS)

HTML_EXTENSIONS:    Final[tuple[str, ...]] = (".html", ".htm", ".xhtml")

HTML_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(HTML_EXTENSIONS)

TEXT_EXTENSIONS: Final[tuple[str, ...]] = (
    ".txt",          ".html",     ".htm",      ".csv",        ".json",       ".xml",
    ".adoc",         ".asciidoc", ".bib",      ".cfg",        ".conf",       ".ini",
    ".log",          ".md",       ".markdown", ".properties", ".rtf",        ".rst",
    ".sgm",          ".sgml",     ".tex",      ".toml",       ".tsv",        ".xhtml",
    ".yaml",         ".yml",      ".svg",      ".rss",        ".atom",       ".opml",
    ".xsd",          ".dtd",      ".xsl",      ".xslt",       ".xaml",       ".kml",
    ".gpx",          ".mml",      ".jsonl",    ".ndjson",     ".geojson",    ".topojson",
    ".ipynb",        ".gltf",     ".mdx",      ".rmd",        ".org",        ".textile",
    ".wiki",         ".mkd",      ".mkdn",     ".mdown",      ".mmd",        ".ltx",
    ".sty",          ".cls",      ".dtx",      ".aux",        ".toc",        ".env",
    ".editorconfig", ".desktop",  ".service",  ".hcl",        ".tf",         ".tfvars",
    ".proto",        ".graphql",  ".gql",      ".cue",        ".rego",       ".edn",
    ".cff",          ".tab",      ".psv",      ".ltsv",       ".css",        ".js",
    ".mjs",          ".cjs",      ".ts",       ".tsx",        ".jsx",        ".ejs",
    ".erb",          ".pug",      ".mustache", ".hbs",        ".handlebars", ".jinja",
    ".jinja2",       ".njk",      ".twig",     ".liquid",     ".sh",         ".bash",
    ".zsh",          ".fish",     ".bat",      ".cmd",        ".ps1",        ".c",
    ".h",            ".cpp",      ".hpp",      ".java",       ".kt",         ".kts",
    ".cs",           ".go",       ".rs",       ".swift",      ".py",         ".rb",
    ".php",          ".pl",       ".lua",      ".r",          ".jl",         ".m",
    ".diff",         ".patch",    ".err",      ".out",        ".po",         ".pot",
    ".ics",          ".vcf",      ".vcard",    ".srt",        ".vtt",        ".ass",
    ".ssa",          ".lrc",      ".dot",      ".gv",         ".mermaid",    ".sgf",
    ".pgn",          ".sfv",      ".md5",      ".sha1",       ".sha256",
)

TEXT_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(TEXT_EXTENSIONS)

BOOK_EXTENSIONS: Final[tuple[str, ...]] = (
    # Open / widely supported ebooks
    ".epub",     # EPUB (most common open ebook format)
    ".pdf",      # PDF (widely used for ebooks, especially textbooks)
    ".txt",      # Plain text
    ".rtf",      # Rich Text Format
    ".html",     # HTML
    ".htm",      # HTML
    ".xhtml",    # XHTML
    ".doc",      # Microsoft Word (legacy binary format)
    ".docx",     # Microsoft Word (modern XML-based format)
    ".odt",      # OpenDocument Text

    # Amazon / Kindle family
    ".azw",      # Kindle (based on MOBI)
    ".azw1",     # Kindle Topaz (legacy)
    ".azw3",     # Kindle KF8
    ".azw4",     # Kindle Print Replica (PDF-like)
    ".azw6",     # Kindle KFX resource container
    ".kfx",      # Kindle KFX
    ".mobi",     # Mobipocket
    ".prc",      # Mobipocket (often identical container)
    ".tpz",      # Kindle Topaz (legacy)

    # Apple iBooks
    ".ibooks",

    # FictionBook
    ".fb2",
    ".fbz",      # zipped FB2

    # DjVu (scanned books)
    ".djvu",
    ".djv",

    # Legacy / less common ebook formats
    ".lit",      # Microsoft Reader
    ".oeb",      # Open eBook
    ".oebzip",   # zipped OEB
    ".pdb",      # Palm/eReader container (various subtypes)
    ".pml",      # Palm Markup Language (often paired with PDB)
    ".pmlz",     # zipped PML
    ".tr2",      # TomeRaider
    ".tr3",      # TomeRaider
    ".rb",       # Rocket eBook
    ".tcr",      # Psion/TECsoft TCR
    ".chm",      # Compiled HTML Help (commonly used for tech ebooks)
    ".snb",      # Shanda Bambook
    ".umd",      # UMD eBook (popular in some regions)

    # Comic-book archives (graphic novels / manga)
    ".cbz",      # ZIP-based
    ".cbr",      # RAR-based
    ".cb7",      # 7z-based
    ".cbt",      # TAR-based
    ".cba",      # ACE-based

    # Sony BBeB family
    ".lrf",      # Sony BBeB
    ".lrx",      # Sony BBeB (encrypted)
    ".lrs",      # Sony BBeB XML source

    # Kobo
    ".kepub",    # Kobo Kepub variant

    # Apple authoring/export
    ".iba",      # iBooks Author package/export
    ".pages",    # Apple Pages document (often used for manuscripts)

    # Apabi / CN markets
    ".ceb",      # Apabi eBook
    ".xeb",      # Apabi eBook (variant)

    # Paginated document formats
    ".xps",      # XML Paper Specification
    ".oxps",     # OpenXPS

    # Print/TeX outputs (often used for books)
    ".ps",       # PostScript
    ".dvi",      # TeX DVI

    # Source/book authoring text formats
    ".tex",      # LaTeX source
    ".rst",      # reStructuredText
    ".md",       # Markdown
    ".markdown",  # Markdown (long extension)

    # Desktop publishing / layout sources
    ".indd",     # Adobe InDesign document
    ".idml",     # Adobe InDesign Markup Language
    ".qxp",      # QuarkXPress project
    ".qxd",      # QuarkXPress document
    ".sla",      # Scribus document
)

BOOK_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(BOOK_EXTENSIONS)

VIDEO_EXTENSIONS: Final[tuple[str, ...]] = (
    ".mp4",    ".mkv",   ".mov",   ".avi",    ".mpg",   ".mpeg",
    ".wmv",    ".m4v",   ".flv",   ".divx",   ".vob",   ".iso",
    ".3gp",    ".webm",  ".mts",   ".m2ts",   ".ts",    ".ogv",
    ".rm",     ".rmvb",  ".asf",   ".f4v",    ".mxf",   ".dv",
    ".swf",    ".m2v",   ".svi",   ".mpe",    ".ogm",   ".bik",
    ".xvid",   ".yuv",   ".qt",    ".gvi",    ".viv",   ".fli",
    ".mjpg",   ".mjpeg", ".amv",   ".drc",    ".flc",   ".vp6",
    ".ivf",    ".mps",   ".vro",   ".hevc",   ".h265",  ".264",
    ".str",    ".evo",   ".3g2",   ".h264",   ".av1",   ".ogx",
    ".mlv",    ".ps",    ".mp2v",  ".dvs",    ".gxf",   ".webp",
    ".vp8",    ".trp",   ".f4p",   ".mk3d",   ".3gpp",  ".mod",
    ".tod",    ".cine",  ".arf",   ".wrf",    ".braw",  ".jmf",
    ".r3d",    ".dpx",   ".mpv",   ".rmx",    ".smk",   ".mj2",
    ".scm",    ".ivr",   ".xesc",  ".wtv",    ".dcr",   ".ismv",
    ".vc1",    ".vcd",   ".bin",   ".sfd",    ".m2t",   ".m2p",
    ".m1v",    ".y4m",   ".dif",   ".dvr-ms", ".tivo",  ".nuv",
    ".nsv",    ".nut",   ".bk2",   ".usm",    ".xmv",   ".thp",
    ".pmf",    ".h263",  ".h261",  ".vp9",    ".mdf",   ".mds",  # Media Descriptor File and Sidecar
    ".nrg",    ".img",   ".toast", ".ccd",    ".b5t",   ".bup",  # Disc/image files
    ".b6t",    ".bwt",   ".cue",   ".ifo",
    ".tp",     ".pvr",   ".rec",   ".tsp",    ".g64",   ".g64x",  # PVR / DVR / CCTV
    ".dav",    ".sec",   ".bvr",   ".dvr",
    ".moflex", ".rpl",   ".mve",  # Game/cutscenes
    ".es",     ".mpv2",  # Raw streams / pro dumps
)

VIDEO_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(VIDEO_EXTENSIONS)

AUDIO_EXTENSIONS: Final[tuple[str, ...]] = (
    ".mp3",   ".wav",   ".flac",  ".aac",   ".ogg",   ".wma",
    ".m4a",   ".alac",  ".aiff",  ".opus",  ".amr",   ".pcm",
    ".au",    ".raw",   ".dts",   ".ac3",   ".mka",   ".mpc",
    ".vqf",   ".ape",   ".shn",   ".ra",    ".rm",    ".oga",
    ".spx",   ".caf",   ".snd",   ".mid",   ".midi",  ".kar",
    ".rmi",   ".asf",   ".wv",    ".mp4",   ".wave",  ".webm",
    ".aa",    ".aax",   ".dsf",   ".dff",   ".sf2",   ".g721",
    ".voc",   ".swa",   ".bwf",   ".ivs",   ".smp",   ".weba",
    ".sds",   ".brstm", ".adx",   ".hca",   ".ast",   ".psf",
    ".psf2",  ".qsf",   ".ssf",   ".usf",   ".gsf",   ".tta",
    ".dsm",   ".dmf",   ".mod",   ".s3m",   ".it",    ".xm",
    ".mt2",   ".mo3",   ".umx",   ".mogg",  ".tak",   ".trk",
    ".669",   ".abc",   ".ts",    ".ym",    ".hsq",   ".mpa",
    ".m4b",   ".m4p",   ".mp2",   ".mp1",   ".aif",   ".aifc",
    ".m4r",   ".adts",  ".eac3",  ".rf64",  ".w64",   ".sd2",
    ".sph",   ".3gp",   ".3g2",   ".3ga",   ".ofr",   ".ofs",
    ".la",    ".pac",   ".mlp",   ".thd",   ".aaxc",  ".dss",
    ".ds2",   ".awb",   ".bcstm", ".bfstm", ".bcwav", ".bfwav",
    ".fsb",   ".wem",   ".xwm",   ".lopus",
)

AUDIO_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(AUDIO_EXTENSIONS)

SUBTITLE_EXTENSIONS: Final[tuple[str, ...]] = (
    ".srt",   ".sub",    ".idx",   ".ass",   ".ssa",   ".vtt",
    ".ttml",  ".dfxp",   ".smi",   ".smil",  ".usf",   ".psb",
    ".mks",   ".lrc",    ".stl",   ".pjs",   ".rt",    ".aqt",
    ".gsub",  ".jss",    ".dks",   ".mpl2",  ".sbt",   ".vsf",
    ".zeg",   ".webvtt", ".scc",   ".cap",   ".asc",   ".sbv",
    ".ebu",   ".sami",   ".xml",   ".itt",   ".txt",   ".sup",
    ".sst",   ".son",    ".mcc",   ".pac",   ".890",   ".mpl",
    ".onl",   ".cin",    ".tds",   ".ult",   ".ttxt",
)

SUBTITLE_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(SUBTITLE_EXTENSIONS)

IMAGE_EXTENSIONS: Final[tuple[str, ...]] = (
    ".bmp",  ".dib",   ".gif",    ".jpeg", ".jpg",  ".jpe",
    ".jfif", ".pjpeg", ".pjp",    ".png",  ".pbm",  ".pgm",
    ".ppm",  ".pnm",   ".pam",    ".tif",  ".tiff", ".sgi",
    ".rgb",  ".tga",   ".hdr",    ".exr",  ".webp", ".apng",
    ".heic", ".heif",  ".avif",   ".jp2",  ".j2k",  ".j2c",
    ".jxr",  ".svg",   ".svgz",   ".eps",  ".ai",   ".pdf",
    ".cdr",  ".emf",   ".wmf",    ".dxf",  ".dwg",  ".mng",
    ".raw",  ".arw",   ".cr2",    ".cr3",  ".dng",  ".erf",
    ".raf",  ".orf",   ".pef",    ".rw2",  ".rwl",  ".sr2",
    ".srw",  ".3fr",   ".kdc",    ".mrw",  ".mos",  ".nrw",
    ".pcx",  ".pcd",   ".pic",    ".pct",  ".xcf",  ".psd",
    ".psb",  ".kra",   ".fit",    ".fits", ".fpx",  ".djvu",
    ".djv",  ".lbm",   ".iff",    ".ico",  ".icns", ".dds",
    ".jxl",  ".xbm",   ".xpm",    ".ras",  ".jpf",  ".jpx",
    ".jpm",  ".qoi",   ".bpg",    ".flif", ".cgm",  ".ktx",
    ".ktx2", ".pvr",   ".basis",  ".nef",  ".crw",  ".dcr",
    ".k25",  ".iiq",   ".fff",    ".mef",  ".x3f",  ".hif",
    ".dcm",  ".nii",   ".gz",     ".nrrd", ".mha",  ".mhd",       # ".gz" matches ".nii.gz"
    ".mrc",  ".sid",   ".ecw",    ".bil",  ".bip",  ".aseprite",
    ".g3",   ".g4",    ".fax",    ".sff",  ".wsq",  ".pspimage",
    ".pdn",  ".psp",   ".ps",     ".ase",  ".clip", ".afphoto",
    ".bsq",
)

IMAGE_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(IMAGE_EXTENSIONS)

PLAYLIST_EXTENSIONS: Final[tuple[str, ...]] = (
    ".m3u",    ".m3u8",    ".pls",  ".xspf",  ".asx",    ".wpl",
    ".zpl",    ".b4s",     ".cue",  ".smil",  ".smi",    ".ram",
    ".wax",    ".wmx",     ".wvx",  ".fpl",   ".mpcpl",  ".dpl",
    ".aimppl", ".aimppl4", ".pla",  ".xml",   ".f4m",    ".ism",
    ".ismv",   ".isml",    ".ismc", ".mpd",
)

PLAYLIST_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(PLAYLIST_EXTENSIONS)

_ARCHIVE_EXTENSIONS_1: tuple[str, ...] = (
    ".zip",     ".rar",    ".7z",    ".tar",    ".gz",      ".tgz",
    ".bz2",     ".xz",     ".tbz2",  ".tz2",    ".lzma",    ".lz",
    ".xpi",     ".crx",    ".zst",   ".cab",    ".arj",     ".ace",
    ".uue",     ".zoo",    ".jar",   ".war",    ".ear",     ".iso",
    ".img",     ".dmg",    ".lzh",   ".lha",    ".cpio",    ".deb",
    ".rpm",     ".apk",    ".pak",   ".arc",    ".a",       ".mar",
    ".b1",      ".wim",    ".shar",  ".run",    ".shk",     ".sit",
    ".sitx",    ".zpaq",   ".br",    ".zipx",   ".xar",     ".dar",
    ".ar",      ".tbz",    ".tb2",   ".txz",    ".tlz",     ".taz",
    ".tzo",     ".tzst",   ".lzo",   ".lz4",    ".phar",    ".asar",
    ".whl",     ".nupkg",  ".gem",   ".crate",  ".conda",   ".ipa",
    ".cbz",     ".cbr",    ".cb7",   ".kmz",    ".warc",    ".pk3",
    ".pk4",     ".alz",    ".cpt",   ".ha",     ".sqx",     ".uha",
    ".z01",     ".r00",    ".001",
)

_ARCHIVE_EXTENSIONS_2: tuple[str, ...] = tuple(f".z{num:02d}" for num in range(2, 100))

_ARCHIVE_EXTENSIONS_3: tuple[str, ...] = tuple(f".r{num:02d}" for num in range(1, 100))

_ARCHIVE_EXTENSIONS_4: tuple[str, ...] = tuple(f".{num:03d}"  for num in range(2, 100))

_ARCHIVE_CATEGORIES = (
    _ARCHIVE_EXTENSIONS_1, _ARCHIVE_EXTENSIONS_2,
    _ARCHIVE_EXTENSIONS_3, _ARCHIVE_EXTENSIONS_4,
)

ARCHIVE_EXTENSIONS: Final[tuple[str, ...]] = tuple(
    dict.fromkeys(chain.from_iterable(_ARCHIVE_CATEGORIES))
)

ARCHIVE_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(ARCHIVE_EXTENSIONS)

_ALL_CATEGORIES = (
    PYTHON_EXTENSIONS, HTML_EXTENSIONS,  TEXT_EXTENSIONS,  BOOK_EXTENSIONS,     SUBTITLE_EXTENSIONS,
    VIDEO_EXTENSIONS,  AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, PLAYLIST_EXTENSIONS, ARCHIVE_EXTENSIONS,
)

ALL_KNOWN_EXTENSIONS: Final[tuple[str, ...]] = tuple(
    dict.fromkeys(chain.from_iterable(_ALL_CATEGORIES))
)

ALL_KNOWN_EXTENSIONS_SET: Final[frozenset[str]] = frozenset(ALL_KNOWN_EXTENSIONS)
