import streamlit as st
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from fpdf import FPDF
import tempfile
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Beam Studio Pro | Web Edition",
    layout="wide",
    page_icon="⚙️",
    initial_sidebar_state="collapsed"
)

# --- CONSTANTS & MATERIALS ---
MATERIALS = {
    "AISI 1020 (Low Carbon)": [295, 380],
    "AISI 1045 (Med Carbon)": [310, 565],
    "AISI 4140 (Alloy Steel)": [655, 1000],
    "Structural Steel (A36)": [250, 400],
    "Custom (Enter Manually)": [0, 0]
}

# --- SESSION STATE INITIALIZATION ---
if 'components' not in st.session_state:
    st.session_state.components = []

# --- PHYSICS ENGINE ---
def get_torque(P_kw, N_rpm):
    if N_rpm <= 0: return 0
    P = P_kw * 1000
    # T = (P * 60) / (2 * pi * N)
    return ((P * 60) / (2 * math.pi * N_rpm)) * 1000

# --- UI LAYOUT ---
st.title("⚙️ Beam Studio Pro | Enterprise Web Edition")
st.markdown("ASME B106.1M Transmission Shaft Design & Analysis Tool")
st.markdown("---")

# Create main layout: Left (Controls) vs Right (Visuals)
col_input, col_viz = st.columns([1, 2])

# ==========================================
# LEFT COLUMN: INPUTS
# ==========================================
with col_input:
    # 1. SPECIFICATIONS CARD
    with st.expander("1. DESIGN SPECIFICATIONS", expanded=True):
        st.caption("System Parameters")
        p_input = st.number_input("Power Input (kW)", value=10.0, step=0.5)
        n_input = st.number_input("Shaft Speed (RPM)", value=500.0, step=10.0)
        len_input = st.number_input("Shaft Length (mm)", value=1000.0, step=50.0)
        
        st.caption("Material Selection")
        mat_choice = st.selectbox("Material", list(MATERIALS.keys()))
        def_sy, def_sut = MATERIALS[mat_choice]
        
        c1, c2 = st.columns(2)
        sy_input = c1.number_input("Yield (Sy)", value=float(def_sy))
        sut_input = c2.number_input("Ultimate (Sut)", value=float(def_sut))
        
        st.caption("ASME Shock Factors")
        f1, f2 = st.columns(2)
        kb_input = f1.number_input("Kb (Bend)", value=1.5)
        kt_input = f2.number_input("Kt (Torsion)", value=1.0)
        keyway_present = st.checkbox("Keyway Present (0.75 factor)", value=True)

    # 2. COMPONENT MANAGER CARD
    with st.expander("2. COMPONENT MANAGER", expanded=True):
        tab_b, tab_g, tab_p = st.tabs(["Bearing", "Gear", "Pulley"])
        
        # BEARING LOGIC
        with tab_b:
            b_pos = st.number_input("Position (mm)", value=0, key="b_p")
            if st.button("Add Bearing", type="primary"):
                st.session_state.components.append({
                    'type': "Bearing", 'pos': b_pos, 'fv': 0, 'fh': 0, 'desc': "Support"
                })
                st.rerun()

        # GEAR LOGIC
        with tab_g:
            g_pos = st.number_input("Position (mm)", value=500, key="g_p")
            c1, c2 = st.columns(2)
            g_teeth = c1.number_input("Teeth (Z)", value=40)
            g_mod = c2.number_input("Module (m)", value=4.0)
            g_press = st.number_input("Pressure Angle (°)", value=20.0)
            g_mesh = st.selectbox("Mesh Location", ["Top", "Bottom", "Right", "Left"])
            
            if st.button("Add Gear", type="primary"):
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
                    
                    st.session_state.components.append({
                        'type': "Gear", 'pos': g_pos, 'fv': fv, 'fh': fh, 
                        'desc': f"Gear Z{int(g_teeth)} m{int(g_mod)}"
                    })
                    st.rerun()

        # PULLEY LOGIC
        with tab_p:
            pu_pos = st.number_input("Position (mm)", value=800, key="p_p")
            pu_dia = st.number_input("Diameter (mm)", value=150)
            pu_fact = st.number_input("Belt Factor", value=1.5)
            pu_dir = st.selectbox("Tension Direction", ["Vertical", "Horizontal"])
            
            if st.button("Add Pulley", type="primary"):
                r = pu_dia / 2
                T_nmm = get_torque(p_input, n_input)
                if r > 0 and T_nmm > 0:
                    F_bend = pu_fact * (T_nmm / r)
                    fv = -F_bend if pu_dir == "Vertical" else 0
                    fh = -F_bend if pu_dir == "Horizontal" else 0
                    st.session_state.components.append({
                        'type': "Pulley", 'pos': pu_pos, 'fv': fv, 'fh': fh, 
                        'desc': f"Pulley D{int(pu_dia)}"
                    })
                    st.rerun()

        # COMPONENT LIST
        st.markdown("#### Active Components")
        if st.session_state.components:
            for i, c in enumerate(st.session_state.components):
                with st.container():
                    col_text, col_del = st.columns([4, 1])
                    info = f"**{c['type']}** @ {int(c['pos'])}mm | V:{int(c['fv'])}N H:{int(c['fh'])}N"
                    col_text.markdown(info)
                    if col_del.button("🗑️", key=f"del_{i}"):
                        del st.session_state.components[i]
                        st.rerun()
            
            if st.button("Clear All", type="secondary"):
                st.session_state.components = []
                st.rerun()
        else:
            st.info("No components added.")

# ==========================================
# RIGHT COLUMN: VISUALIZATION & ANALYSIS
# ==========================================
with col_viz:
    st.header("3. ANALYSIS DASHBOARD")
    
    # --- MATPLOTLIB SETUP (DARK MODE FOR UI) ---
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(10, 12))
    gs = fig.add_gridspec(4, 1, height_ratios=[1, 1, 1, 1.5])
    
    ax_cad = fig.add_subplot(gs[0])
    ax1 = fig.add_subplot(gs[1], sharex=ax_cad)
    ax2 = fig.add_subplot(gs[2], sharex=ax_cad)
    ax3 = fig.add_subplot(gs[3], sharex=ax_cad)

    # --- DRAW SCHEMATIC ---
    ax_cad.set_ylim(-80, 80)
    ax_cad.set_xlim(-50, len_input + 50)
    ax_cad.axis('off')
    ax_cad.set_title("SHAFT CONFIGURATION", color="white", fontweight="bold")
    
    # Shaft Body
    ax_cad.plot([-20, len_input+20], [0, 0], '-.', color="#555", lw=1)
    ax_cad.add_patch(patches.Rectangle((0, -10), len_input, 20, fc="#7f8c8d", alpha=0.9))
    
    # Draw Components
    for c in st.session_state.components:
        x = c['pos']
        if c['type'] == "Bearing":
            ax_cad.add_patch(patches.Polygon([[x, -10], [x-10, -25], [x+10, -25]], fc="#3498db"))
            ax_cad.text(x, -38, "Brg", ha='center', color="#3498db", fontsize=9)
        elif c['type'] == "Gear":
            ax_cad.add_patch(patches.Rectangle((x-10, -40), 20, 80, fc="#e74c3c", alpha=0.7, ec="white"))
            ax_cad.text(x, 50, "Gear", ha='center', color="#e74c3c", fontsize=9)
        elif c['type'] == "Pulley":
            ax_cad.add_patch(patches.Rectangle((x-15, -30), 30, 60, fc="#2ecc71", alpha=0.7, ec="white"))
            ax_cad.text(x, 40, "Pulley", ha='center', color="#2ecc71", fontsize=9)

    # --- CALCULATION LOGIC ---
    bearings = sorted([c for c in st.session_state.components if c['type'] == "Bearing"], key=lambda x: x['pos'])
    
    if len(bearings) == 2:
        b1, b2 = bearings[0], bearings[1]
        L_span = b2['pos'] - b1['pos']
        
        if L_span > 0:
            # Solve Reactions
            def solve_reactions(key):
                m_sum = sum(c[key] * (c['pos'] - b1['pos']) for c in st.session_state.components if c['type']!="Bearing")
                f_sum = sum(c[key] for c in st.session_state.components if c['type']!="Bearing")
                Rb = -m_sum / L_span
                Ra = -f_sum - Rb
                return Ra, Rb

            Rav, Rbv = solve_reactions('fv')
            Rah, Rbh = solve_reactions('fh')
            
            # Generate Moment Arrays
            x_vals = np.arange(0, len_input + 1, 5)
            M_v, M_h, M_res = [], [], []
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

            # --- PLOT GRAPHS (UI) ---
            def plot_line(ax, y_data, color, label):
                y_scaled = [y/1000 for y in y_data] # Convert to Nm
                ax.plot(x_vals, y_scaled, color=color, lw=1.5)
                ax.fill_between(x_vals, y_scaled, color=color, alpha=0.2)
                ax.grid(True, color="#444", linestyle=':')
                ax.text(0.02, 0.9, label, transform=ax.transAxes, color=color, fontweight='bold')
            
            plot_line(ax1, M_v, "#00e5ff", "VERTICAL BENDING (Nm)")
            plot_line(ax2, M_h, "#e040fb", "HORIZONTAL BENDING (Nm)")
            plot_line(ax3, M_res, "#ffea00", f"RESULTANT (Max: {max_M/1000:.1f} Nm)")
            
            st.pyplot(fig)

            # --- RESULTS BOX ---
            T_nmm = get_torque(p_input, n_input)
            tau_allow = min(0.3*sy_input, 0.18*sut_input)
            if keyway_present: tau_allow *= 0.75
            
            M_eq = math.sqrt( (kb_input*max_M)**2 + (kt_input*T_nmm)**2 )
            d_req = ((16*M_eq)/(math.pi*tau_allow))**(1/3) if tau_allow > 0 else 0
            
            st.success(f"### ✅ CALCULATED DIAMETER: {d_req:.3f} mm")
            st.info(f"Torque: {T_nmm/1000:.2f} Nm | Max Moment: {max_M/1000:.2f} Nm | Allowable Shear: {tau_allow:.2f} MPa")

            # ==========================================
            # FPDF REPORT GENERATION
            # ==========================================
            def generate_pdf():
                pdf = FPDF()
                pdf.add_page()
                
                # HEADER
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "BEAM STUDIO PRO | ENGINEERING REPORT", ln=True, align='C')
                pdf.set_font("Arial", "I", 10)
                pdf.cell(0, 10, "ASME B106.1M Transmission Shaft Analysis", ln=True, align='C')
                pdf.line(10, 30, 200, 30)
                pdf.ln(10)

                # SECTION 1: DATA
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, "1. DESIGN PARAMETERS", ln=True)
                pdf.set_font("Arial", "", 10)
                
                col_w = 45
                pdf.cell(col_w, 8, f"Power: {p_input} kW", 1)
                pdf.cell(col_w, 8, f"Speed: {n_input} RPM", 1)
                pdf.cell(col_w, 8, f"Torque: {T_nmm/1000:.1f} Nm", 1)
                pdf.cell(col_w, 8, f"Length: {len_input} mm", 1, 1)
                
                pdf.cell(col_w, 8, f"Mat: {mat_choice[:15]}...", 1)
                pdf.cell(col_w, 8, f"Yield: {sy_input} MPa", 1)
                pdf.cell(col_w, 8, f"Ult: {sut_input} MPa", 1)
                pdf.cell(col_w, 8, f"Shear Allow: {tau_allow:.1f}", 1, 1)
                pdf.ln(5)

                # SECTION 2: COMPONENTS
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, "2. LOAD INVENTORY", ln=True)
                
                pdf.set_fill_color(240, 240, 240)
                pdf.set_font("Arial", "B", 9)
                headers = ["Type", "Pos (mm)", "Vert Force (N)", "Horz Force (N)", "Description"]
                widths = [25, 20, 30, 30, 85]
                
                for w, h in zip(widths, headers):
                    pdf.cell(w, 8, h, 1, 0, 'C', fill=True)
                pdf.ln()
                
                pdf.set_font("Arial", "", 9)
                for c in st.session_state.components:
                    pdf.cell(widths[0], 8, str(c['type']), 1)
                    pdf.cell(widths[1], 8, str(int(c['pos'])), 1)
                    pdf.cell(widths[2], 8, str(int(c['fv'])), 1)
                    pdf.cell(widths[3], 8, str(int(c['fh'])), 1)
                    pdf.cell(widths[4], 8, str(c['desc']), 1, 1)
                pdf.ln(5)

                # SECTION 3: GRAPHS (Clean White Background for PDF)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, "3. MOMENT DIAGRAMS", ln=True)
                
                with plt.style.context('default'):
                    fig_pdf = plt.figure(figsize=(8, 6))
                    gs_pdf = fig_pdf.add_gridspec(3, 1)
                    ax_p1 = fig_pdf.add_subplot(gs_pdf[0])
                    ax_p2 = fig_pdf.add_subplot(gs_pdf[1])
                    ax_p3 = fig_pdf.add_subplot(gs_pdf[2])
                    
                    # Re-plot for PDF (white bg)
                    ax_p1.plot(x_vals, [y/1000 for y in M_v], 'b'); ax_p1.set_ylabel("Vert (Nm)"); ax_p1.grid(True)
                    ax_p2.plot(x_vals, [y/1000 for y in M_h], 'g'); ax_p2.set_ylabel("Horz (Nm)"); ax_p2.grid(True)
                    ax_p3.plot(x_vals, [y/1000 for y in M_res], 'r'); ax_p3.set_ylabel("Res (Nm)"); ax_p3.grid(True)
                    
                    plt.tight_layout()
                    
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                        fig_pdf.savefig(tmpfile.name, dpi=150)
                        tmp_name = tmpfile.name
                    
                    # Embed and delete
                    pdf.image(tmp_name, x=10, w=190)
                    os.unlink(tmp_name)

                # SECTION 4: RESULT
                pdf.ln(5)
                pdf.set_fill_color(220, 255, 220)
                pdf.rect(10, pdf.get_y(), 190, 15, 'DF')
                pdf.set_y(pdf.get_y() + 4)
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 8, f"MINIMUM SHAFT DIAMETER REQUIRED: {d_req:.3f} mm", align='C')

                return pdf.output(dest='S').encode('latin-1')

            # --- DOWNLOAD BUTTON ---
            pdf_bytes = generate_pdf()
            st.download_button(
                label="📥 Download Professional Report (PDF)",
                data=pdf_bytes,
                file_name="BeamStudio_Report.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        else:
            st.warning("⚠️ Component Span Error: Overlapping or Reversed Bearings.")
    else:
        st.pyplot(fig)
        st.warning("⚠️ SETUP INCOMPLETE: Please add exactly 2 Bearings to calculate.")
