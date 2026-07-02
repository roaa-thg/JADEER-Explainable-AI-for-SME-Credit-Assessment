"""
جدير core logic — simple and transparent.
Turns a bank statement (transactions) into 5 signals, then into a 0-100 score.
No black box: every signal's contribution is visible (that's our explainability).
"""
import os
import pandas as pd

FEATURES = ["net_cashflow", "stability_cv", "growth_pct", "min_balance", "red_flags"]
_MODEL = None
_MODEL_LOADED = False


def _load_model():
    """Load the trained XGBoost model once (if it exists). No model -> rule-based fallback."""
    global _MODEL, _MODEL_LOADED
    if not _MODEL_LOADED:
        _MODEL_LOADED = True
        if os.path.exists("credit_model.json"):
            from xgboost import XGBClassifier
            _MODEL = XGBClassifier()
            _MODEL.load_model("credit_model.json")
    return _MODEL


def ml_score(sig):
    """Score any statement with the trained model -> 0..100 (higher = safer). None if no model."""
    m = _load_model()
    if m is None:
        return None
    import numpy as np
    x = np.array([[sig[f] for f in FEATURES]], dtype=float)
    p_default = float(m.predict_proba(x)[0, 1])
    return round((1 - p_default) * 100)

# how much each signal counts toward the final score (must sum to 1.0)
WEIGHTS = {
    "capacity":  0.35,   # can they cover the installment? (most important)
    "liquidity": 0.20,   # do they keep a cash buffer?
    "stability": 0.15,   # is income steady or jumpy?
    "growth":    0.15,   # is the business trending up or down?
    "redflags":  0.15,   # bounced payments, overdraft, late fees
}


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def compute_signals(df, loan_amount=None, term_months=None):
    """Read transactions -> signal values.
    loan_amount/term_months come from the SME's application (the requested loan)."""
    df = df.copy()
    df["month"] = df["date"].str[:7]
    monthly = df.groupby("month").agg(credit=("credit", "sum"), debit=("debit", "sum"))
    income = monthly["credit"]

    # net OPERATING cash flow: real surplus, excluding owner capital injections
    op = df[~df["description"].str.contains("إيداع رأس مال من المالك", na=False)]
    opm = op.groupby("month").agg(credit=("credit", "sum"), debit=("debit", "sum"))
    net_cashflow = (opm["credit"] - opm["debit"]).mean()

    # installment (المقدّر) = requested amount / term — "can they afford the NEW loan?"
    if loan_amount and term_months:
        installment = loan_amount / term_months
        installment_source = "مقدّر (المبلغ ÷ المدة)"
    else:
        inst = df[df["description"].str.contains("قسط تمويل", na=False)]["debit"]
        installment = inst.mean() if len(inst) else 8000
        installment_source = "من الكشف"

    return {
        "avg_income": round(income.mean()),
        "net_cashflow": round(net_cashflow),
        "installment": round(installment),
        "installment_source": installment_source,
        "capacity_dscr": round(net_cashflow / installment, 1),       # surplus covers the new installment X times
        "stability_cv": round(income.std() / income.mean(), 2),      # lower = steadier
        "growth_pct": round((income.tail(3).mean() - income.head(3).mean()) / income.head(3).mean() * 100, 1),
        "min_balance": round(df["balance"].min()),
        "neg_count": int((df["balance"] < 0).sum()),
        "red_flags": int(df["description"].str.contains("مرتجع|مكشوف|تأخر", na=False).sum()),
    }


def score_company(sig, use_model=True):
    """5 signals -> 5 sub-scores (0-100) -> one weighted score + breakdown.
    Headline score comes from the trained ML model when available; the transparent
    sub-scores/reasons explain the drivers. Falls back to rules if no model."""
    sub = {
        "capacity":  clamp((sig["net_cashflow"] + 8000) / 20000 * 100),  # surplus: +12k->100, deficit->low
        "stability": clamp((1 - sig["stability_cv"]) * 100),         # CV 0->100, 1+->0
        "growth":    clamp((sig["growth_pct"] + 40) / 50 * 100),     # -40%->0, +10%->100
        "liquidity": clamp((sig["min_balance"] + 30000) / 80000 * 100),
        "redflags":  clamp(100 - sig["red_flags"] * 10),             # each flag -10
    }
    rule_score = round(sum(WEIGHTS[k] * sub[k] for k in WEIGHTS))
    m_score = ml_score(sig) if use_model else None
    score = m_score if m_score is not None else rule_score
    score_source = "نموذج ذكاء اصطناعي (XGBoost)" if m_score is not None else "تقييم شفّاف بأوزان"

    if score >= 70:
        band, reco = "مخاطر منخفضة", "موافقة مبدئية بالمبلغ المطلوب"
    elif score >= 40:
        band, reco = "مخاطر متوسطة", "موافقة مشروطة بضمان كفالة (يغطّي حتى ٩٠٪)"
    else:
        band, reco = "مخاطر عالية", "تحويل لكفالة مع متابعة، أو رفض"

    # readable labels for the dashboard
    labels = {"capacity": "القدرة على السداد", "liquidity": "السيولة",
              "stability": "استقرار الدخل", "growth": "اتجاه النمو", "redflags": "الإشارات الحمراء"}
    details = {
        "capacity": (f"صافي تدفق تشغيلي {sig['net_cashflow']:,} ﷼/شهر · يغطّي القسط ×{sig['capacity_dscr']}"
                     if sig['net_cashflow'] >= 0 else
                     f"عجز تشغيلي {sig['net_cashflow']:,} ﷼/شهر (يعتمد على تمويل خارجي)"),
        "liquidity": f"أدنى رصيد {sig['min_balance']:,} ﷼ · دخل السالب {sig['neg_count']} مرات",
        "stability": f"معامل التذبذب {sig['stability_cv']} (أقل = أثبت)",
        "growth": f"اتجاه الإيرادات {sig['growth_pct']}%",
        "redflags": f"{sig['red_flags']} حالة (مرتجعات / سحب على المكشوف)",
    }
    breakdown = [
        {"signal": labels[k], "sub_score": round(sub[k]),
         "effect": "+" if sub[k] >= 60 else ("-" if sub[k] < 40 else "•"),
         "detail": details[k]}
        for k in WEIGHTS
    ]
    breakdown.sort(key=lambda r: r["sub_score"], reverse=True)

    reasons = build_reasons(sig, sub)
    suggestions = build_suggestions(sig, sub, score)
    return {"score": score, "band": band, "recommendation": reco, "score_source": score_source,
            "breakdown": breakdown, "reasons": reasons, "suggestions": suggestions}


def build_reasons(sig, sub):
    """Plain-language 'why' — one sentence per signal, chosen by the numbers."""
    r = []
    if sub["capacity"] >= 60:
        r.append(f"القدرة جيدة: صافي تدفق تشغيلي موجب {sig['net_cashflow']:,} ﷼/شهر يغطّي القسط.")
    else:
        r.append(f"القدرة ضعيفة: صافي التدفق التشغيلي {sig['net_cashflow']:,} ﷼/شهر — فائض غير كافٍ للقسط الجديد.")
    if sub["stability"] >= 60:
        r.append("الدخل مستقر شهرياً (تذبذب منخفض).")
    else:
        r.append(f"الدخل متذبذب (معامل تذبذب {sig['stability_cv']}) — يصعّب توقّع السداد.")
    if sig["growth_pct"] >= 5:
        r.append(f"الإيرادات في اتجاه صاعد ({sig['growth_pct']}%).")
    elif sig["growth_pct"] >= -10:
        r.append(f"الإيرادات مستقرة تقريباً ({sig['growth_pct']}%).")
    else:
        r.append(f"الإيرادات في اتجاه هابط ({sig['growth_pct']}%) — مؤشر ضعف.")
    if sig["min_balance"] >= 0 and sig["neg_count"] == 0:
        r.append("السيولة صحّية: الرصيد لم يدخل السالب طوال الفترة.")
    else:
        r.append(f"ضعف سيولة: الرصيد دخل السالب {sig['neg_count']} مرات (أدنى رصيد {sig['min_balance']:,} ﷼).")
    if sig["red_flags"] == 0:
        r.append("لا توجد إشارات حمراء (لا شيكات مرتجعة ولا سحب على المكشوف).")
    else:
        r.append(f"إشارات حمراء: {sig['red_flags']} حالة (شيكات مرتجعة / سحب على المكشوف / تأخّر سداد).")
    return r


def build_suggestions(sig, sub, score):
    """Actionable next steps for the bank and for the SME."""
    bank, sme = [], []
    if score >= 70:
        bank.append("موافقة مبدئية بالمبلغ المطلوب مع متابعة دورية.")
    elif score >= 40:
        bank.append("موافقة بمبلغ مخفّض (≈ ٧٠٪ من المطلوب) لتقليل المخاطر.")
        bank.append("اشتراط ضمان أو كفالة (برنامج كفالة يغطّي حتى ٩٠٪).")
    else:
        bank.append("تأجيل الموافقة أو ربطها بضمان قوي / كفالة.")
        bank.append("طلب قوائم مالية مدققة قبل القرار.")
    if sub["capacity"] < 60:
        sme.append("رفع صافي التدفق النقدي أو تقليل مبلغ التمويل المطلوب.")
    if sig["red_flags"] > 0:
        sme.append("معالجة الدفعات المرتجعة والسحب على المكشوف لرفع الجدارة.")
    if sub["stability"] < 60:
        sme.append("تنويع مصادر الدخل لتقليل الاعتماد على عميل واحد.")
    if not sme:
        sme.append("الحفاظ على الأداء الحالي؛ المؤشرات صحّية.")
    return {"bank": bank, "sme": sme}


if __name__ == "__main__":
    for name, path in [("السليمة", "healthy_company_statement.csv"),
                       ("المتعثرة", "risky_company_statement.csv")]:
        df = pd.read_csv(path)
        sig = compute_signals(df)
        res = score_company(sig)
        print(f"\n=== {name} ===")
        print("signals:", sig)
        print("SCORE:", res["score"], "|", res["band"], "|", res["recommendation"])
        for b in res["breakdown"]:
            print(f"   {b['effect']} {b['signal']}: {b['sub_score']}")
