import streamlit as st
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import io

# --- PAGE CONFIGURATION (Dark Theme applied via Streamlit settings usually, but we force plot styles) ---
st.set_page_config(page_title="Beam Studio Pro | Web Edition", layout="wide", page_icon="⚙️")

# --- CONSTANTS ---
MATERIALS = {
    "AISI 1020 (Low Carbon)": [295, 380],
    "AISI 1045 (Med Carbon)": [310, 565],
    "AISI 4140 (Alloy Steel)": [655, 1000],
    "Structural Steel (A36)": [250, 400],
    "Custom": [0, 0]
}

# --- SESSION STATE (Memory for the web app) ---
if 'components' not in st.session_state:
    st.session_state.components = []

# --- HELPER FUNCTIONS ---
def get_torque(P_kw, N_rpm):
    if N_rpm <= 0: return 0
    P = P_kw * 1000
    return ((P * 60) / (2 * math.pi * N_rpm)) * 1000

# --- MAIN APP LAYOUT ---
st.title("⚙️ Beam Studio Pro | ASME B106.1M | Web Edition")

# Create two columns: Left for Inputs, Right for Visualization
col_inputs, col_viz = st.columns([1, 2])

with col_inputs:
    with st.expander("1. DESIGN SPECIFICATIONS", expanded=True):
        st.markdown("### System Parameters")
        p_input = st.number_input("Power Input (kW)", value=10.0, step=0.5)
        n_input = st.number_input("Shaft Speed (RPM)", value=500.0, step=10.0)
        len_input = st.number_input("Shaft Length (mm)", value=1000.0, step=50.0)
        
        st.markdown("### Material")
        mat_choice = st.selectbox("Select Material", list(MATERIALS.keys()))
        # Auto-fill yield/ultimate based on selection
        def_sy, def_sut = MATERIALS[mat_choice]
        
        c1, c2 = st.columns(2)
        sy_input = c1.number_input("Yield (Sy) MPa", value=float(def_sy))
        sut_input = c2.number_input("Ult (Sut) MPa", value=float(def_sut))
        
        st.markdown("### Factors")
        f1, f2 = st.columns(2)
        kb_input = f1.number_input("Kb (Bend)", value=1.5)
        kt_input = f2.number_input("Kt (Torsion)", value=1.0)
        keyway_present = st.checkbox("Keyway Present (Reduces strength 25%)", value=True)

    with st.expander("2. COMPONENT MANAGER", expanded=True):
        tab_b, tab_g, tab_p = st.tabs(["Bearing", "Gear", "Pulley"])
        
        # --- BEARING ADDER ---
        with tab_b:
            b_pos = st.number_input("Bearing Pos (mm)", value=0)
            if st.button("Add Support"):
                st.session_state.components.append({'type':"Bearing", 'pos':b_pos, 'fv':0, 'fh':0, 'desc':"Support"})
                st.success(f"Added Bearing at {b_pos}")

        # --- GEAR ADDER ---
        with tab_g:
            g_pos = st.number_input("Gear Pos (mm)", value=500)
            g_teeth = st.number_input("Teeth (Z)", value=40)
            g_mod = st.number_input("Module (m)", value=4.0)
            g_press = st.number_input("Pressure Angle", value=20.0)
            g_mesh = st.selectbox("Mesh Location", ["Top", "Right", "Bottom", "Left"])
            
            if st.button("Add Gear"):
                radius = (g_teeth * g_mod) / 2
                T_nmm = get_torque(p_input, n_input)
                if radius > 0 and T_nmm > 0:
                    Ft = T_nmm / radius
                    Fr = Ft * math.tan(math.radians(g_press))
                    fv, fh = 0, 0
                    if g_mesh == "Top": fh, fv = Ft, -Fr
                    elif g_mesh == "Bottom": fh, fv = -Ft, Fr
                    elif g_mesh == "Right": fh, fv = -Fr, Ft
                    elif g_mesh == "Left": fh, fv = Fr, -Ft
                    
                    st.session_state.components.append({'type':"Gear", 'pos':g_pos, 'fv':fv, 'fh':fh, 'desc':f"Z{g_teeth} m{g_mod}"})
                    st.success("Gear Added")

        # --- PULLEY ADDER ---
        with tab_p:
            pu_pos = st.number_input("Pulley Pos (mm)", value=800)
            pu_dia = st.number_input("Diameter (mm)", value=150)
            pu_fact = st.number_input("Belt Factor", value=1.5)
            pu_dir = st.selectbox("Tension Direction", ["Vertical", "Horizontal"])
            
            if st.button("Add Pulley"):
                r = pu_dia / 2
                T_nmm = get_torque(p_input, n_input)
                if r > 0 and T_nmm > 0:
                    F_bend = pu_fact * (T_nmm / r)
                    fv = -F_bend if pu_dir == "Vertical" else 0
                    fh = -F_bend if pu_dir == "Horizontal" else 0
                    st.session_state.components.append({'type':"Pulley", 'pos':pu_pos, 'fv':fv, 'fh':fh, 'desc':f"D{int(pu_dia)}"})
                    st.success("Pulley Added")

        # --- COMPONENT LIST ---
        st.markdown("---")
        st.markdown("**Active Components:**")
        if st.session_state.components:
            for i, c in enumerate(st.session_state.components):
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.text(f"{c['type']} @ {c['pos']}mm")
                c2.text(f"V:{int(c['fv'])} H:{int(c['fh'])}")
                if c3.button("❌", key=f"del_{i}"):
                    del st.session_state.components[i]
                    st.rerun()
            
            if st.button("Reset All Components"):
                st.session_state.components = []
                st.rerun()
        else:
            st.info("No components added.")

# --- CALCULATION LOGIC ---
bearings = sorted([c for c in st.session_state.components if c['type'] == "Bearing"], key=lambda x: x['pos'])
is_valid_setup = len(bearings) == 2

with col_viz:
    st.header("3. ANALYSIS & VISUALIZATION")
    
    # Setup Plotting
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(10, 12))
    gs = fig.add_gridspec(4, 1, height_ratios=[1, 1, 1, 1.5])
    ax_cad = fig.add_subplot(gs[0])
    ax1 = fig.add_subplot(gs[1], sharex=ax_cad)
    ax2 = fig.add_subplot(gs[2], sharex=ax_cad)
    ax3 = fig.add_subplot(gs[3], sharex=ax_cad)

    # DRAW SCHEMATIC
    ax_cad.set_ylim(-80, 80)
    ax_cad.set_xlim(-50, len_input + 50)
    ax_cad.axis('off')
    ax_cad.set_title("SHAFT SCHEMATIC", color="white")
    ax_cad.plot([-20, len_input+20], [0, 0], '-.', color="#555", lw=1)
    ax_cad.add_patch(patches.Rectangle((0, -10), len_input, 20, fc="#7f8c8d", alpha=0.8))
    
    for c in st.session_state.components:
        x = c['pos']
        if c['type'] == "Bearing":
            ax_cad.add_patch(patches.Polygon([[x, -10], [x-10, -25], [x+10, -25]], fc="#3498db"))
            ax_cad.text(x, -35, "Brg", ha='center', color="#3498db", fontsize=8)
        elif c['type'] == "Gear":
            ax_cad.add_patch(patches.Rectangle((x-10, -40), 20, 80, fc="#e74c3c", alpha=0.6))
            ax_cad.text(x, 45, "Gear", ha='center', color="#e74c3c", fontsize=8)
        elif c['type'] == "Pulley":
            ax_cad.add_patch(patches.Rectangle((x-15, -30), 30, 60, fc="#2ecc71", alpha=0.6))
            ax_cad.text(x, 35, "Pulley", ha='center', color="#2ecc71", fontsize=8)

    # RUN CALCULATIONS IF VALID
    if is_valid_setup:
        b1, b2 = bearings[0], bearings[1]
        L_span = b2['pos'] - b1['pos']
        
        if L_span > 0:
            def solve_r(key):
                m_sum = sum(c[key] * (c['pos'] - b1['pos']) for c in st.session_state.components if c['type']!="Bearing")
                f_sum = sum(c[key] for c in st.session_state.components if c['type']!="Bearing")
                Rb = -m_sum / L_span
                Ra = -f_sum - Rb
                return Ra, Rb

            Rav, Rbv = solve_r('fv')
            Rah, Rbh = solve_r('fh')
            
            x_vals = range(0, int(len_input) + 1, 5)
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
                M_v.append(mv)
                M_h.append(mh)
                M_res.append(res)
                if res > max_M: max_M = res

            # PLOT GRAPHS
            def style_plot(ax, data, color, title):
                y = [d/1000 for d in data]
                ax.plot(x_vals, y, color=color, lw=1.5)
                ax.fill_between(x_vals, y, color=color, alpha=0.2)
                ax.set_facecolor("#2b2b2b")
                ax.grid(True, color="#444", linestyle=':')
                ax.text(0.02, 0.9, title, transform=ax.transAxes, color=color, fontweight='bold', fontsize=9)

            style_plot(ax1, M_v, "#00e5ff", "VERTICAL BENDING (Nm)")
            style_plot(ax2, M_h, "#e040fb", "HORIZONTAL BENDING (Nm)")
            style_plot(ax3, M_res, "#ffea00", f"RESULTANT (Max: {max_M/1000:.1f} Nm)")
            
            st.pyplot(fig)
            
            # --- RESULTS & PDF ---
            T_nmm = get_torque(p_input, n_input)
            tau_allow = min(0.3*sy_input, 0.18*sut_input)
            if keyway_present: tau_allow *= 0.75
            
            M_eq = math.sqrt( (kb_input*max_M)**2 + (kt_input*T_nmm)**2 )
            d_req = ((16*M_eq)/(math.pi*tau_allow))**(1/3) if tau_allow > 0 else 0
            
            st.success(f"### ✅ MIN DIAMETER REQUIRED: {d_req:.3f} mm")
            
            # PDF GENERATION LOGIC
            def create_pdf():
                buffer = io.BytesIO()
                with PdfPages(buffer) as pdf:
                    # Page 1: Data
                    fig_p1 = plt.figure(figsize=(8.5, 11))
                    ax = fig_p1.add_subplot(111); ax.axis('off')
                    
                    # Header
                    ax.add_patch(patches.Rectangle((0, 0.9), 1, 0.1, transform=ax.transAxes, fc="#2c3e50"))
                    ax.text(0.5, 0.95, "BEAM STUDIO PRO - REPORT", ha='center', va='center', transform=ax.transAxes, fontsize=20, color='white', fontweight='bold')
                    
                    info_text = (
                        f"Input Power:   {p_input} kW\n"
                        f"Shaft Speed:   {n_input} RPM\n"
                        f"Design Torque: {T_nmm/1000:.2f} Nm\n"
                        f"Material:      {mat_choice}\n"
                        f"Shear Allow:   {tau_allow:.2f} MPa"
                    )
                    ax.text(0.1, 0.8, "1. PARAMETERS", fontsize=14, fontweight='bold')
                    ax.text(0.1, 0.75, info_text, va='top', family='monospace')
                    
                    # Table
                    y = 0.5
                    ax.text(0.1, y, "2. LOADS", fontsize=14, fontweight='bold')
                    row_y = y - 0.05
                    for c in st.session_state.components:
                        line = f"{c['type']:<10} @ {c['pos']}mm | V:{int(c['fv'])} H:{int(c['fh'])}"
                        ax.text(0.1, row_y, line, family='monospace'); row_y -= 0.03
                    
                    # Result
                    ax.add_patch(patches.Rectangle((0.1, 0.1), 0.8, 0.15, transform=ax.transAxes, fc="#ecf0f1", ec="black"))
                    ax.text(0.5, 0.2, f"MIN DIAMETER: {d_req:.4f} mm", ha='center', transform=ax.transAxes, fontsize=20, fontweight='bold', color='#c0392b')
                    pdf.savefig(fig_p1)
                    
                    # Page 2: Graphs (Switch to light theme for printing)
                    plt.style.use('default')
                    
                    # We need to redraw the graphs for the PDF to ensure they look good on white paper
                    fig_pdf = plt.figure(figsize=(8.5, 11))
                    gs_pdf = fig_pdf.add_gridspec(3, 1)
                    ax_pdf1 = fig_pdf.add_subplot(gs_pdf[0])
                    ax_pdf2 = fig_pdf.add_subplot(gs_pdf[1])
                    ax_pdf3 = fig_pdf.add_subplot(gs_pdf[2])
                    
                    ax_pdf1.plot(x_vals, [d/1000 for d in M_v], 'b'); ax_pdf1.set_title("Vertical Moment")
                    ax_pdf2.plot(x_vals, [d/1000 for d in M_h], 'g'); ax_pdf2.set_title("Horizontal Moment")
                    ax_pdf3.plot(x_vals, [d/1000 for d in M_res], 'r'); ax_pdf3.set_title("Resultant Moment")
                    
                    plt.tight_layout()
                    pdf.savefig(fig_pdf)
                    
                buffer.seek(0)
                return buffer

            # DOWNLOAD BUTTON
            pdf_bytes = create_pdf()
            st.download_button(
                label="📥 Download Detailed PDF Report",
                data=pdf_bytes,
                file_name="Shaft_Design_Report.pdf",
                mime="application/pdf"
            )

    else:
        st.warning("⚠️ Please add exactly 2 Bearings to run the simulation.")
        st.pyplot(fig)
