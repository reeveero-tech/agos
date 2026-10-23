"""AGOS Intelligence Platform - Universal Engineering Intelligence.

المدخل المعتمد (ADR-0009 — R-W1-006): هذه الحزمة سقالة رؤيوية متخصصة (عقود
السجل/الموجّه/الأنطولوجيا/إدراك الأدوات كما هي — G2)؛ و**مدخل التشغيل**
للذكاء الموحد يفوّض إلى الواجهة المرجعية في النواة
``agos_kernel.intelligence.interface`` — لا محرك موازٍ هنا (R-W3-019 يعتمد
على هذا الربط).
"""


def run_intelligence(request):
    """تفويض حي إلى **النسخة المرجعية نفسها** — المدخل الموحد للأنماط
    الثلاثة (Instant/Engineer/Research — ADR-0009). معرّف الاعتماد الذي
    يعوده هذا المدخل تعتمده النسخة المرجعية وتنفّذه (لا نسخة موازية)."""
    return get_intelligence_interface().run(request)


def get_intelligence_interface():
    """الواجهة المرجعية نفسها (تبنى مرة ويعاد استخدامها — سلسلة حية واحدة)."""
    from agos_kernel.intelligence.interface import IntelligenceInterface
    global _INTELLIGENCE_INTERFACE
    try:
        return _INTELLIGENCE_INTERFACE
    except NameError:
        _INTELLIGENCE_INTERFACE = IntelligenceInterface()
        return _INTELLIGENCE_INTERFACE
