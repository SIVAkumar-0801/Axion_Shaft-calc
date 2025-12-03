import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math
from matplotlib.backends.backend_pdf import PdfPages
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="AXION | The Shaft Architect", layout="wide", page_icon="⚓")

# --- CUSTOM STYLES (Dark Mode Optimization) ---
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    .stButton>button {
        background-color: #27ae60;
        color: white;
        border-radius: 5px;
        font-weight: bold;
    }
    /* Make the title look more 'peculiar' and distinct */
    h1 {
        font-family: 'Courier New', monospace;
        color: #3498db;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONSTANTS ---
COLORS = {
    "shaft": "#95a5a6",
    "gear": "#e74c3c", 
    "pulley": "#3498db",
    "bearing": "#f1c40f",
    "v_plot": "#00e5ff",
    "h_plot": "#e040fb",
    "res_plot": "#ffea00"
}

MATERIALS = {
    "AISI 1020 (Low Carbon)": [295, 380],
    "AISI 1045 (Med Carbon)": [310, 565],
    "AISI 4140 (Alloy Steel)": [655, 1000],
    "Structural Steel (A36)": [250, 400],
}

# --- STATE MANAGEMENT ---
if 'components' not in st.session_state:
    st.session_state.components = []

# --- HELPER FUNCTIONS ---
def get_torque(power_kw, speed_rpm):
    if speed_rpm <= 0: return 0
    # T = (P * 60) / (2 * pi * N) * 1000 (for N-mm)
    return ((power_kw * 1000 * 60) / (2 * math.pi * speed_rpm)) * 1000

def add_component(c_type, pos, fv, fh, details):
    st.session_state.components.append({
        "type": c_type, "pos": pos, "fv": fv, "fh": fh, "details": details
    })

def remove_component(index):
    if 0 <= index < len(st.session_state.components):
        st.session_state.components.pop(index)

def reset_system():
    st.session_state.components = []

# --- SIDEBAR: INPUTS ---
with st.sidebar:
    st.header("⚙️ Design Specs")
    
    with st.expander("Global Parameters", expanded=True):
        P = st.number_input("Power (kW)", value=10.0, step=0.5)
        N = st.number_input("Speed (RPM)", value=500.0, step=10.0)
        L = st.number_input("Shaft Length (mm)", value=1000.0, step=50.0)
        
        mat_name = st.selectbox("Material", list(MATERIALS.keys()))
        Sy, Sut = MATERIALS[mat_name]
        st.caption(f"Sy: {Sy} MPa | Sut: {Sut} MPa")
        
        col1, col2 = st.columns(2)
        Kb = col1.number_input("Kb (Bend)", value=1.5)
        Kt = col2.number_input("Kt (Torsion)", value=1.0)
        
        keyway = st.checkbox("Keyway Present (-25%)", value=True)

    st.header("🔧 Components")
    
    tab1, tab2, tab3 = st.tabs(["Bearing", "Gear", "Pulley"])
    
    with tab1:
        b_pos = st.number_input("Bearing Pos (mm)", 0, int(L), 0)
        if st.button("Add Bearing"):
            add_component("Bearing", b_pos, 0, 0, "Support")
            
    with tab2:
        g_pos = st.number_input("Gear Pos (mm)", 0, int(L), 500)
        g_z = st.number_input("Teeth", 10, 200, 40)
        g_m = st.number_input("Module", 1, 20, 4)
        g_alpha = st.number_input("Pressure Angle", 14.5, 25.0, 20.0)
        g_mesh = st.selectbox("Mesh Loc", ["Top", "Bottom", "Right", "Left"])
        
        if st.button("Add Gear"):
            r = (g_z * g_m) / 2
            T = get_torque(P, N)
            if r > 0 and T > 0:
                Ft = T / r
                Fr = Ft * math.tan(math.radians(g_alpha))
                fv, fh = 0, 0
                if g_mesh == "Top": fh, fv = Ft, -Fr
                elif g_mesh == "Bottom": fh, fv = -Ft, Fr
                elif g_mesh == "Right": fh, fv = -Fr, Ft
                elif g_mesh == "Left": fh, fv = Fr, -Ft
                add_component("Gear", g_pos, fv, fh, f"Z{g_z} m{g_m}")

    with tab3:
        p_pos = st.number_input("Pulley Pos (mm)", 0, int(L), 800)
        p_d = st.number_input("Diameter (mm)", 10, 1000, 150)
        p_fac = st.number_input("Belt Factor", 1.0, 3.0, 1.5)
        p_dir = st.selectbox("Tension Dir", ["Vertical", "Horizontal"])
        
        if st.button("Add Pulley"):
            r = p_d / 2
            T = get_torque(P, N)
            if r > 0 and T > 0:
                F_bend = p_fac * (T/r)
                fv = -F_bend if p_dir == "Vertical" else 0
                fh = -F_bend if p_dir == "Horizontal" else 0
                add_component("Pulley", p_pos, fv, fh, f"D{p_d}")

    st.divider()
    st.subheader("Active Assembly")
    if st.session_state.components:
        for i, c in enumerate(st.session_state.components):
            col1, col2 = st.columns([4, 1])
            col1.text(f"{c['type']} @ {c['pos']}mm")
            if col2.button("X", key=f"del_{i}"):
                remove_component(i)
                st.rerun()
    else:
        st.info("No components added.")
    
    if st.button("Reset System"):
        reset_system()
        st.rerun()

# --- MAIN PAGE: VISUALIZATION ---
st.title("AXION | The Shaft Architect")
st.caption("Advanced Transmission Analysis Engine | ASME B106.1M Standard")

# 1. Schematic Logic
fig_sch, ax = plt.subplots(figsize=(10, 2))
ax.set_facecolor('#0e1117') # Match Streamlit Dark
fig_sch.patch.set_facecolor('#0e1117')
ax.plot([-50, L+50], [0, 0], '-.', color='gray', lw=1)
ax.add_patch(patches.Rectangle((0, -10), L, 20, fc=COLORS['shaft'], ec='white', alpha=0.8))

for c in st.session_state.components:
    x = c['pos']
    if c['type'] == "Bearing":
        ax.add_patch(patches.Polygon([[x, -10], [x-10, -25], [x+10, -25]], fc=COLORS['bearing']))
    elif c['type'] == "Gear":
        ax.add_patch(patches.Rectangle((x-10, -40), 20, 80, fc=COLORS['gear'], alpha=0.7))
        ax.text(x, 45, "Gear", color='white', ha='center', fontsize=8)
    elif c['type'] == "Pulley":
        ax.add_patch(patches.Rectangle((x-15, -30), 30, 60, fc=COLORS['pulley'], alpha=0.7))
        ax.text(x, 35, "Pulley", color='white', ha='center', fontsize=8)

ax.set_ylim(-60, 60)
ax.set_xlim(-50, L+50)
ax.axis('off')
st.pyplot(fig_sch)

# 2. Calculation Engine
bearings = sorted([c for c in st.session_state.components if c['type'] == "Bearing"], key=lambda x: x['pos'])

if len(bearings) == 2:
    b1, b2 = bearings[0], bearings[1]
    L_span = b2['pos'] - b1['pos']
    
    if L_span > 0:
        # Solve Reactions
        def solve_r(key):
            m_sum = sum(c[key] * (c['pos'] - b1['pos']) for c in st.session_state.components if c['type']!="Bearing")
            f_sum = sum(c[key] for c in st.session_state.components if c['type']!="Bearing")
            Rb = -m_sum / L_span
            Ra = -f_sum - Rb
            return Ra, Rb

        Rav, Rbv = solve_r('fv')
        Rah, Rbh = solve_r('fh')
        
        # Integrate Moments
        x_vals = range(0, int(L)+1, 5)
        M_res, M_v, M_h = [], [], []
        max_M = 0
        
        for x in x_vals:
            mv, mh = 0, 0
            if x > b1['pos']: mv += Rav*(x-b1['pos']); mh += Rah*(x-b1['pos'])
            if x > b2['pos']: mv += Rbv*(x-b2['pos']); mh += Rbh*(x-b2['pos'])
            for c in st.session_state.components:
                if c['type']!="Bearing" and x > c['pos']:
                    mv += c['fv']*(x-c['pos']); mh += c['fh']*(x-c['pos'])
            
            res = math.sqrt(mv**2 + mh**2)
            M_v.append(mv); M_h.append(mh); M_res.append(res)
            if res > max_M: max_M = res

        # 3. Graphs
        st.subheader("Structural Analysis")
        fig_g, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
        fig_g.patch.set_facecolor('#0e1117')
        
        def style_ax(ax, data, color, title):
            ax.set_facecolor('#0e1117')
            ax.plot(x_vals, [d/1000 for d in data], color=color)
            ax.fill_between(x_vals, [d/1000 for d in data], color=color, alpha=0.2)
            ax.grid(True, color='#444444', linestyle=':')
            ax.set_ylabel("Nm", color='white')
            ax.set_title(title, color=color, fontsize=10, loc='left')
            ax.tick_params(colors='white')
            for spine in ax.spines.values(): spine.set_color('#555555')

        style_ax(ax1, M_v, COLORS['v_plot'], "Vertical Bending Moment (Pv)")
        style_ax(ax2, M_h, COLORS['h_plot'], "Horizontal Bending Moment (Ph)")
        style_ax(ax3, M_res, COLORS['res_plot'], f"Resultant Moment (Max: {max_M/1000:.1f} Nm)")
        
        st.pyplot(fig_g)
        
        # 4. ASME Calculation
        T_nmm = get_torque(P, N)
        tau_allow = min(0.3*Sy, 0.18*Sut)
        if keyway: tau_allow *= 0.75
        
        M_eq = math.sqrt( (Kb*max_M)**2 + (Kt*T_nmm)**2 )
        d_req = ((16*M_eq)/(math.pi*tau_allow))**(1/3) if tau_allow > 0 else 0

        # 5. Results & Report
        st.success(f"### Minimum Shaft Diameter: {d_req:.3f} mm")
        
        col_res1, col_res2 = st.columns(2)
        col_res1.info(f"**Max Moment:** {max_M/1000:.2f} Nm\n\n**Design Torque:** {T_nmm/1000:.2f} Nm")
        col_res2.info(f"**Allowable Shear:** {tau_allow:.2f} MPa\n\n**Material:** {mat_name}")

        # PDF Export Logic
        def create_pdf():
            buffer = io.BytesIO()
            with PdfPages(buffer) as pdf:
                # Page 1: Data
                fig_text = plt.figure(figsize=(8.5, 11))
                plt.axis('off')
                txt = (f"AXION | SHAFT ARCHITECT\n"
                       f"ASME B106.1M ENGINEERING REPORT\n"
                       f"===============================\n\n"
                       f"Power: {P} kW | Speed: {N} RPM\n"
                       f"Material: {mat_name}\n\n"
                       f"RESULTS:\n"
                       f"--------\n"
                       f"Min Diameter: {d_req:.3f} mm\n"
                       f"Max Moment:   {max_M/1000:.2f} Nm\n"
                       f"Design Torque:{T_nmm/1000:.2f} Nm")
                plt.text(0.1, 0.7, txt, fontsize=12, family='monospace')
                pdf.savefig(fig_text)
                # Page 2: Graphs
                pdf.savefig(fig_g)
            buffer.seek(0)
            return buffer

        pdf_data = create_pdf()
        st.download_button(label="📄 Download AXION Report (PDF)", 
                           data=pdf_data, 
                           file_name="AXION_Shaft_Report.pdf", 
                           mime="application/pdf")

    else:
        st.error("Bearings must be at different positions.")
else:
    st.warning("Please add exactly 2 Bearings to run the simulation.")
