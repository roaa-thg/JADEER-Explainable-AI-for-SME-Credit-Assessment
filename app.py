"""
جدير — Officer Dashboard (Streamlit). Colors come from .streamlit/config.toml
Run:  streamlit run app.py
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from smartlend import compute_signals, score_company

st.set_page_config(page_title="جدير", page_icon="🏦", layout="wide")

# structure + RTL only; COLORS are driven by .streamlit/config.toml theme variables
st.markdown("""<style>
.stApp,section[data-testid="stSidebar"]{direction:rtl;text-align:right;}
/* force RTL on ALL Streamlit widgets, labels, inputs, radios, selects */
.stApp *, section[data-testid="stSidebar"] *{direction:rtl;}
label, .stMarkdown, .stSelectbox, .stTextInput, .stNumberInput, .stRadio, .stFileUploader,
[data-testid="stWidgetLabel"], [data-baseweb="select"], [data-testid="stMarkdownContainer"]{
  text-align:right !important; direction:rtl !important;}
[data-testid="stWidgetLabel"] p{text-align:right !important;}
.stRadio [role="radiogroup"]{align-items:flex-end;}
input, textarea{text-align:right !important;direction:rtl !important;}
.stButton>button{direction:rtl;}
.block-container{padding:1rem 1.6rem 0.6rem;max-width:100%;}
#MainMenu,footer,header{visibility:hidden;}
div[data-testid="stHorizontalBlock"]{gap:0.9rem;}
.card{background:var(--secondary-background-color);border-radius:18px;padding:16px 18px;height:100%;
      box-shadow:0 2px 12px rgba(0,0,0,.06);border:1px solid #E6ECF3;}
.pt{font-size:16px;font-weight:700;color:var(--primary-color);margin:0 0 12px;}
.big{font-size:66px;font-weight:800;line-height:1;}
.pill{display:inline-block;padding:6px 20px;border-radius:20px;font-size:15px;font-weight:700;margin-top:8px;color:#fff;}
.k{background:rgba(0,0,0,.10);border-radius:14px;padding:10px 12px;text-align:center;}
.k b{font-size:20px;}.k span{font-size:12.5px;opacity:.75;}
.bar .top{display:flex;justify-content:space-between;font-size:14px;margin-bottom:4px;}
.bar .track{height:8px;background:rgba(0,0,0,.14);border-radius:5px;overflow:hidden;margin-bottom:3px;}
.bar .fill{height:100%;border-radius:5px;}
.bar .note{font-size:12px;opacity:.7;margin-bottom:9px;}
.row{font-size:14px;margin:5px 0;line-height:1.6;}
.chk{font-size:14px;color:#1e7d34;margin:3px 0;font-weight:600;}
.info{font-size:14px;margin:4px 0;display:flex;justify-content:space-between;border-bottom:1px solid rgba(0,0,0,.12);padding-bottom:4px;}
.info span{opacity:.7;}
.reco{font-size:15px;font-weight:700;padding:9px 12px;border-radius:12px;margin-bottom:6px;color:#fff;}
.sub{font-size:14px;font-weight:700;color:var(--primary-color);margin:8px 0 2px;}
.emp{text-align:right;}
.emp .n{font-size:20px;font-weight:800;}
.emp .t{font-size:15px;font-weight:600;margin-top:2px;}
.emp .b{font-size:15px;opacity:.7;margin-top:2px;}
</style>""", unsafe_allow_html=True)

DEMO = {
    "مؤسسة الأمل التجارية": {"file": "healthy_company_statement.csv", "sector": "تجارة تجزئة", "cr": "4030112233", "amount": 200000, "purpose": "رأس مال عامل", "term": 24},
    "مؤسسة الواحة للخدمات": {"file": "medium_company_statement.csv", "sector": "خدمات", "cr": "4030445566", "amount": 120000, "purpose": "توسعة", "term": 18},
    "شركة النجم للمقاولات": {"file": "risky_company_statement.csv", "sector": "مقاولات", "cr": "4030778899", "amount": 150000, "purpose": "تمويل مشاريع", "term": 36},
}
# low=green, medium=amber(primary), high=red
BAND = {"مخاطر منخفضة": "#22C55E", "مخاطر متوسطة": "#F39C12", "مخاطر عالية": "#EF4444"}

with st.sidebar:
    st.markdown("## 🏦 جدير")
    mode = st.radio("المصدر", ["شركة من القائمة", "➕ إضافة شركة جديدة"], label_visibility="collapsed")
    if mode == "شركة من القائمة":
        choice = st.selectbox("طلبات التمويل", list(DEMO.keys()))
        m = DEMO[choice]; name, sector, cr = choice, m["sector"], m["cr"]
        df = pd.read_csv(m["file"])
        amount = st.number_input("مبلغ التمويل المطلوب (﷼)", value=m["amount"], step=10000)
        term = st.number_input("مدة السداد (أشهر)", value=m["term"], step=6, min_value=6)
    else:
        st.markdown("**بيانات الشركة الجديدة**")
        name = st.text_input("اسم الشركة", "شركة تجريبية")
        sector = st.text_input("القطاع", "تجزئة")
        cr = st.text_input("رقم السجل التجاري", "4030000000")
        up = st.file_uploader("رفع كشف حساب (CSV)", type="csv")
        amount = st.number_input("مبلغ التمويل المطلوب (﷼)", value=100000, step=10000)
        term = st.number_input("مدة السداد (أشهر)", value=24, step=6, min_value=6)
        df = pd.read_csv(up) if up else None
    st.markdown("---")
    st.markdown('<div class="emp"><div class="n">👤 رؤى القحطاني</div>'
                '<div class="t">موظف ائتمان المنشآت</div><div class="b">الفرع: جدة</div></div>', unsafe_allow_html=True)

if df is None:
    st.markdown("#### ➕ إضافة شركة جديدة")
    st.info("أدخل بيانات الشركة وارفع كشف حساب CSV — وسيقيّمها النموذج مباشرة.")
    st.stop()

sig = compute_signals(df, loan_amount=amount, term_months=term)
res = score_company(sig)
bc = BAND[res["band"]]

st.markdown(f"#### {name} — طلب تمويل: {amount:,} ﷼ · {term} شهر")

c1, c2, c3 = st.columns([1.05, 1.15, 1.3])

with c1:
    st.markdown(f"""<div class="card" style="text-align:center;">
      <div style="font-size:15px;opacity:.7;">درجة الائتمان</div>
      <div class="big" style="color:{bc};">{res['score']}</div>
      <div class="pill" style="background:{bc};">{res['band']}</div>
      <div style="margin-top:10px;font-size:14px;">التوصية: <b>{res['recommendation']}</b></div>
      <div style="display:flex;gap:8px;margin-top:14px;">
        <div class="k" style="flex:1;"><b>{amount:,}</b><br><span>مبلغ التمويل ﷼</span></div>
        <div class="k" style="flex:1;"><b>{sig['installment']:,}</b><br><span>القسط الشهري ﷼</span></div></div>
      <div style="display:flex;gap:8px;margin-top:8px;">
        <div class="k" style="flex:1;"><b style="color:{'#1e7d34' if sig['net_cashflow']>=0 else '#c0392b'}">{sig['net_cashflow']:,}</b><br><span>صافي التدفق ﷼</span></div>
        <div class="k" style="flex:1;"><b style="color:{'#c0392b' if sig['red_flags'] else '#1e7d34'}">{sig['red_flags']}</b><br><span>إشارات حمراء</span></div></div>
    </div>""", unsafe_allow_html=True)

with c2:
    bars = ""
    for b in res["breakdown"]:
        col = {"+": "#22C55E", "•": "#F39C12", "-": "#EF4444"}[b["effect"]]
        bars += f"""<div class="bar"><div class="top"><span>{b['signal']}</span><span style="color:{col};font-weight:700">{b['sub_score']}</span></div>
          <div class="track"><div class="fill" style="width:{b['sub_score']}%;background:{col};"></div></div><div class="note">{b['detail']}</div></div>"""
    st.markdown(f'<div class="card"><div class="pt">العوامل المؤثرة</div>{bars}</div>', unsafe_allow_html=True)

with c3:
    info = f"""<div class="info"><span>القطاع</span><b>{sector}</b></div>
      <div class="info"><span>رقم السجل التجاري</span><b>{cr}</b></div>"""
    checks = "".join(f'<div class="chk">✔ {t}</div>' for t in ["السجل التجاري — موثّق", "استعلام سمة — سجل نظيف", "شهادة حجم المنشأة — صغيرة"])
    reasons = "".join(f'<div class="row">• {r}</div>' for r in res["reasons"])
    st.markdown(f"""<div class="card">
      <div class="pt">معلومات الشركة والتحقق</div>{info}<div style="margin:6px 0 2px;">{checks}</div>
      <div class="pt" style="margin-top:12px;">الأسباب</div>{reasons}
      <div class="reco" style="background:{bc};margin-top:8px;">{res['recommendation']}</div></div>""", unsafe_allow_html=True)

# chart
tmp = df.copy(); tmp["month"] = tmp["date"].str[:7]
bal = tmp.groupby("month")["balance"].last().reset_index()
bal.columns = ["الشهر", "الرصيد"]
st.markdown('<div style="font-size:14px;font-weight:700;color:var(--primary-color);font-size:16px;margin:12px 0 4px;">كشف الحساب — الرصيد الشهري</div>', unsafe_allow_html=True)
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=bal["الشهر"], y=bal["الرصيد"],
    mode="lines+markers",
    line=dict(color="#2E86C1", width=3),
    marker=dict(size=7, color="#2E86C1"),
    fill="tozeroy",
    fillcolor="rgba(46,134,193,0.15)",
    name="الرصيد"
))
fig.add_hline(y=0, line_dash="dash", line_color="#C0392B", line_width=1.5)
fig.update_layout(
    height=220, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0,r=0,t=0,b=0), showlegend=False,
    xaxis=dict(tickangle=-40, gridcolor="rgba(0,0,0,0.05)", color="#1A2433"),
    yaxis=dict(gridcolor="rgba(0,0,0,0.05)", color="#1A2433", title="ريال")
)
st.plotly_chart(fig, use_container_width=True)

# decision buttons (bottom row, no box, no title)
d1, d2, d3 = st.columns(3)
if d1.button("✅ موافقة", width="stretch"): st.success("تم تسجيل القرار: موافقة")
if d2.button("📄 طلب مستندات إضافية", width="stretch"): st.info("تم تسجيل القرار: طلب مستندات")
if d3.button("❌ رفض", width="stretch"): st.error("تم تسجيل القرار: رفض")
