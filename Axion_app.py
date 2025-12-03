import streamlit as st
import pandas as pd
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from fpdf import FPDF
import tempfile
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Kinetic Nexus | Web Edition",
    layout="wide",
    page_icon="⚛️",
    initial_sidebar_state="expanded"
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
if 'run_analysis' not in st.session_state:
    st.session_state.run_analysis = False

# --- PHYSICS ENGINE ---
def get_torque(P_kw, N_rpm):
    """Calculates Torque in N-mm from Power (kW) and Speed (RPM)"""
    if N_rpm <= 0: return 0
    P = P_kw * 1000 # Convert to Watts
    # T = (P * 60) / (2 * pi * N)
    return ((P * 60) / (2 * math.pi * N_rpm)) * 1000

# --- UI LAYOUT ---
st.title("⚛️ KINETIC NEXUS | Design Engine")
st.markdown("**Advanced Rotational Physics & Shaft Architecture Tool**")
st.markdown("---")

# Create main layout: Left (Controls) vs Right (Visuals)
col_input, col_viz = st.columns([1, 1.5])

# ==========================================
# LEFT COLUMN: INPUTS
# ==========================================
with col_input:
    # 1. SPECIFICATIONS CARD
    with st.expander("1. KINETIC PARAMETERS", expanded=True):
        st.caption("System Inputs")
        c1, c2 = st.columns(2)
        p_input = c1.number_input("Power (kW)", value=10.0, step=0.5)
        n_input = c2.number_input("Speed (RPM)", value=500.0, step=10.0)
        len_input = st.number_input("Shaft Length (mm)", value=1000.0, step=50.0)
        
        st.caption("Material Matrix")
        mat_choice = st.selectbox("Material Class", list(MATERIALS.keys()))
        def_sy, def_sut = MATERIALS[mat_choice]
        
        c3, c4 = st.columns(2)
        sy_input = c3.number_input("Yield (Sy)", value=float(def_sy))
        sut_input = c4.number_input("Ultimate (Sut)", value=float(def_sut))
        
        st.caption("Safety Coefficients (ASME)")
        f1, f2 = st.columns(2)
        kb_input = f1.number_input("Kb (Bend)", value=1.5)
        kt_input = f2.number_input("Kt (Torsion)", value=1.0)
        keyway_present = st.checkbox("Keyway Geometry (0.75 shear factor)", value=True)

    # 2. COMPONENT MANAGER CARD
    with st.expander("2. LOAD CONFIGURATOR", expanded=True):
        tab_b, tab_g, tab_p = st.tabs(["Bearing", "Gear", "Pulley"])
        
        # BEARING LOGIC
        with tab_b:
            b_pos = st.number_input("Position (mm)", value=0, key="b_p")
            if st.button("Initialize Bearing", type="primary"):
                st.session_state.components.append({
                    'type': "Bearing", 'pos': b_pos, 'fv': 0, 'fh': 0, 'desc': "Support"
                })
                st.session_state.run_analysis = False # Reset analysis on change
                st.rerun()

        # GEAR LOGIC
        with tab_g:
            g_pos = st.number_input("Position (mm)", value=500, key="g_p")
            c1, c2 = st.columns(2)
            g_teeth = c1.number_input("Teeth (Z)", value=40)
            g_mod = c2.number_input("Module (m)", value=4.0)
            g_press = st.number_input("Pressure (°)", value=20.0)
            g_mesh = st.selectbox("Mesh Loc", ["Top", "Bottom", "Right", "Left"])
            
            if st.button("Mount Gear", type="primary"):
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
                        'desc': f"Z{int(g_teeth)} m{int(g_mod)}"
                    })
                    st.session_state.run_analysis = False # Reset analysis on change
                    st.rerun()

        # PULLEY LOGIC
        with tab_p:
            pu_pos = st.number_input("Position (mm)", value=800, key="p_p")
            pu_dia = st.number_input("Diameter (mm)", value=150)
            pu_fact = st.number_input("Belt Factor", value=1.5)
            pu_dir = st.selectbox("Tension Dir", ["Vertical", "Horizontal"])
            
            if st.button("Mount Pulley", type="primary"):
                r = pu_dia / 2
                T_nmm = get_torque(p_input, n_input)
                if r > 0 and T_nmm > 0:
                    F_bend = pu_fact * (T_nmm / r)
                    fv = -F_bend if pu_dir == "Vertical" else 0
                    fh = -F_bend if pu_dir == "Horizontal" else 0
                    st.session_state.components.append({
                        'type': "Pulley", 'pos': pu_pos, 'fv': fv, 'fh': fh, 
                        'desc': f"Dia {int(pu_dia)}"
                    })
                    st.session_state.run_analysis = False # Reset analysis on change
                    st.rerun()

        # COMPONENT TABLE (PANDAS INTEGRATION)
        st.markdown("#### 📋 System Inventory")
        if st.session_state.components:
            # 1. Create DataFrame
            df = pd.DataFrame(st.session_state.components)
            
            # 2. Format for Display (Select specific columns and rename)
            display_df = df[['type', 'pos', 'fv', 'fh', 'desc']].copy()
            display_df.columns = ["Element", "Axial Pos", "V-Load", "H-Load", "Specs"]
            
            # 3. Show Table
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            # 4. Deletion Controls
            with st.expander("🗑️ Dismantle Components"):
                for i, c in enumerate(st.session_state.components):
                    c_txt, c_btn = st.columns([4, 1])
                    c_txt.text(f"{c['type']} @ {c['pos']}mm")
                    if c_btn.button("Purge", key=f"del_{i}"):
                        del st.session_state.components[i]
                        st.session_state.run_analysis = False # Reset analysis on change
                        st.rerun()
                
                if st.button("Reset Nexus", type="secondary"):
                    st.session_state.components = []
                    st.session_state.run_analysis = False
                    st.rerun()
        else:
            st.info("Nexus is empty. Initialize components above.")

    # --- MAIN ACTION BUTTON ---
    st.markdown("---")
    # This button triggers the visibility of the results
    if st.button("⚡ ACTIVATE SIMULATION CORE", type="primary", use_container_width=True):
        st.session_state.run_analysis = True
        st.rerun()

# ==========================================
# RIGHT COLUMN: VISUALIZATION & ANALYSIS
# ==========================================
with col_viz:
    st.header("3. ANALYTICAL READOUT")
    
    # --- MATPLOTLIB SETUP (DARK MODE FOR UI) ---
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(10, 12))
    gs = fig.add_gridspec(4, 1, height_ratios=[1, 1, 1, 1.5])
    
    ax_cad = fig.add_subplot(gs[0])
    ax1 = fig.add_subplot(gs[1], sharex=ax_cad)
    ax2 = fig.add_subplot(gs[2], sharex=ax_cad)
    ax3 = fig.add_subplot(gs[3], sharex=ax_cad)

    # --- DRAW SCHEMATIC (ALWAYS VISIBLE) ---
    # We want users to see the setup before they run the math
    ax_cad.set_ylim(-80, 80)
    ax_cad.set_xlim(-50, len_input + 50)
    ax_cad.axis('off')
    ax_cad.set_title("GEOMETRIC TOPOLOGY", color="white", fontweight="bold")
    
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

    # --- CALCULATION LOGIC (ONLY IF BUTTON PRESSED) ---
    if st.session_state.run_analysis:
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
                
                st.success(f"### ✅ MINIMUM DIAMETER: {d_req:.3f} mm")
                
                with st.expander("See Calculation Details"):
                    st.write(f"**Torque:** {T_nmm/1000:.2f} Nm")
                    st.write(f"**Max Bending Moment:** {max_M/1000:.2f} Nm")
                    st.write(f"**Allowable Shear:** {tau_allow:.2f} MPa")
                    st.write(f"**Reaction A:** V:{int(Rav)}N / H:{int(Rah)}N")
                    st.write(f"**Reaction B:** V:{int(Rbv)}N / H:{int(Rbh)}N")

                # ==========================================
                # FPDF REPORT GENERATION (MATCHING REPORT2.PDF)
                # ==========================================
                def generate_pdf():
                    pdf = FPDF()
                    
                    # --- PAGE 1: DATA SHEET ---
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 16)
                    pdf.cell(0, 10, "DESIGN DATA SHEET", ln=True, align='C')
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(0, 10, "ASME B106.1M Shaft Analysis", ln=True, align='C')
                    pdf.line(10, 30, 200, 30)
                    pdf.ln(10)

                    # 1. GLOBAL PARAMETERS
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(0, 8, "1. GLOBAL PARAMETERS", ln=True)
                    pdf.set_font("Arial", "", 10)
                    
                    # Use a grid-like text dump for parameters
                    p_text = f"Power: {p_input} kW\nSpeed: {n_input} RPM\nTorque: {T_nmm/1000:.2f} Nm\nLength: {len_input} mm\nMaterial: {mat_choice}"
                    pdf.multi_cell(0, 6, p_text)
                    pdf.ln(5)

                    # 2. COMPONENT LOADS
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(0, 8, "2. COMPONENT LOADS", ln=True)
                    
                    # Table Header
                    pdf.set_fill_color(240, 240, 240)
                    pdf.set_font("Arial", "B", 9)
                    headers = ["TYPE", "POS (mm)", "F_VERT (N)", "F_HORZ (N)"]
                    w = [40, 30, 40, 40]
                    for i, h in enumerate(headers):
                        pdf.cell(w[i], 8, h, 1, 0, 'C', fill=True)
                    pdf.ln()
                    
                    # Table Rows
                    pdf.set_font("Arial", "", 9)
                    for c in st.session_state.components:
                        pdf.cell(w[0], 8, str(c['type']), 1)
                        pdf.cell(w[1], 8, str(int(c['pos'])), 1)
                        pdf.cell(w[2], 8, str(int(c['fv'])), 1)
                        pdf.cell(w[3], 8, str(int(c['fh'])), 1, 1)
                    pdf.ln(5)

                    # 3. CALCULATED REACTIONS
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(0, 8, "3. CALCULATED REACTIONS", ln=True)
                    pdf.set_font("Arial", "", 10)
                    
                    # Reaction A
                    pdf.cell(40, 6, "Bearing A (Left):", 0)
                    pdf.cell(50, 6, f"Vert: {Rav:.1f} N", 0)
                    pdf.cell(50, 6, f"Horz: {Rah:.1f} N", 0, 1)
                    
                    # Reaction B
                    pdf.cell(40, 6, "Bearing B (Right):", 0)
                    pdf.cell(50, 6, f"Vert: {Rbv:.1f} N", 0)
                    pdf.cell(50, 6, f"Horz: {Rbh:.1f} N", 0, 1)
                    
                    # --- PAGE 2: IMAGES ---
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 14)
                    pdf.cell(0, 10, "SHAFT LAYOUT & MOMENT DIAGRAMS", ln=True, align='C')
                    pdf.ln(5)
                    
                    # Temporarily switch plot style to WHITE for printing
                    with plt.style.context('default'):
                        fig_pdf = plt.figure(figsize=(8, 10)) # Taller figure
                        gs_pdf = fig_pdf.add_gridspec(4, 1, height_ratios=[1, 1, 1, 1.2])
                        
                        ax_p0 = fig_pdf.add_subplot(gs_pdf[0])
                        ax_p1 = fig_pdf.add_subplot(gs_pdf[1])
                        ax_p2 = fig_pdf.add_subplot(gs_pdf[2])
                        ax_p3 = fig_pdf.add_subplot(gs_pdf[3])
                        
                        # Schematic on PDF
                        ax_p0.set_title("Shaft Layout Model", fontsize=9)
                        ax_p0.set_xlim(-50, len_input+50); ax_p0.set_ylim(-50, 50)
                        ax_p0.axis('off')
                        ax_p0.plot([-20, len_input+20], [0, 0], '-.', color='black', lw=0.5)
                        ax_p0.add_patch(patches.Rectangle((0, -5), len_input, 10, fc='lightgray', ec='black'))
                        # Add components to schematic
                        for c in st.session_state.components:
                            cx = c['pos']
                            if c['type'] == "Bearing":
                                ax_p0.add_patch(patches.Polygon([[cx, -5], [cx-5, -15], [cx+5, -15]], fc='white', ec='black'))
                                ax_p0.text(cx, -20, "Brg", ha='center', fontsize=6)
                            elif c['type'] in ["Gear", "Pulley"]:
                                color = 'salmon' if c['type']=="Gear" else 'skyblue'
                                ax_p0.add_patch(patches.Rectangle((cx-5, -20), 10, 40, fc=color, alpha=0.5))
                                ax_p0.text(cx, 22, c['type'], ha='center', fontsize=6)

                        # Graphs
                        ax_p1.plot(x_vals, [y/1000 for y in M_v], 'b'); ax_p1.set_ylabel("Vert (Nm)"); ax_p1.grid(True, alpha=0.3)
                        ax_p1.set_title("Vertical Bending Moment", fontsize=8, color='blue', loc='left')
                        ax_p1.fill_between(x_vals, [y/1000 for y in M_v], color='blue', alpha=0.1)
                        
                        ax_p2.plot(x_vals, [y/1000 for y in M_h], 'g'); ax_p2.set_ylabel("Horz (Nm)"); ax_p2.grid(True, alpha=0.3)
                        ax_p2.set_title("Horizontal Bending Moment", fontsize=8, color='green', loc='left')
                        ax_p2.fill_between(x_vals, [y/1000 for y in M_h], color='green', alpha=0.1)

                        ax_p3.plot(x_vals, [y/1000 for y in M_res], 'r'); ax_p3.set_ylabel("Res (Nm)"); ax_p3.grid(True, alpha=0.3)
                        ax_p3.set_title(f"Resultant Moment (Max: {max_M/1000:.1f} Nm)", fontsize=8, color='red', loc='left')
                        ax_p3.fill_between(x_vals, [y/1000 for y in M_res], color='red', alpha=0.1)

                        plt.tight_layout()
                        
                        # Save & Embed
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                            fig_pdf.savefig(tmpfile.name, dpi=150)
                            tmp_name = tmpfile.name
                        
                        pdf.image(tmp_name, x=10, y=40, w=190)
                        os.unlink(tmp_name)

                    # --- PAGE 3: DETAILED CALCULATIONS ---
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(0, 10, "DETAILED CALCULATIONS", ln=True)
                    pdf.ln(5)

                    # A. Allowable Stress
                    pdf.set_font("Arial", "B", 10)
                    pdf.cell(0, 6, "A. Allowable Stress (Tau)", ln=True)
                    pdf.set_font("Arial", "", 10)
                    base_tau = min(0.3*sy_input, 0.18*sut_input)
                    pdf.cell(0, 6, f"Sy: {sy_input} MPa, Sut: {sut_input} MPa", ln=True)
                    pdf.cell(0, 6, f"Base Tau = min(0.3*Sy, 0.18*Sut) = {base_tau:.1f} MPa", ln=True)
                    pdf.cell(0, 6, f"Keyway Factor = {0.75 if keyway_present else 1.0}", ln=True)
                    pdf.cell(0, 6, f"Final Tau_allow = {tau_allow:.2f} MPa", ln=True)
                    pdf.ln(5)

                    # B. Equivalent Moment
                    pdf.set_font("Arial", "B", 10)
                    pdf.cell(0, 6, "B. Equivalent Moment (M_eq)", ln=True)
                    pdf.set_font("Arial", "", 10)
                    pdf.cell(0, 6, f"Max Bending (M) = {max_M/1000:.1f} Nm", ln=True)
                    pdf.cell(0, 6, f"Torque (T) = {T_nmm/1000:.1f} Nm", ln=True)
                    pdf.cell(0, 6, f"Shock Factors: Kb={kb_input}, Kt={kt_input}", ln=True)
                    pdf.cell(0, 6, f"M_eq = sqrt( (Kb*M)^2 + (Kt*T)^2 )", ln=True)
                    pdf.cell(0, 6, f"M_eq = {M_eq/1000:.1f} Nm", ln=True)
                    pdf.ln(5)

                    # C. Diameter
                    pdf.set_font("Arial", "B", 10)
                    pdf.cell(0, 6, "C. Diameter Calculation", ln=True)
                    pdf.set_font("Arial", "", 10)
                    pdf.cell(0, 6, "d = [ (16 * M_eq) / (pi * Tau) ] ^ (1/3)", ln=True)
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(0, 10, f"d = {d_req:.3f} mm", ln=True)

                    return pdf.output(dest='S').encode('latin-1')

                # --- DOWNLOAD BUTTON ---
                pdf_bytes = generate_pdf()
                st.download_button(
                    label="📥 Download Design Data Sheet (PDF)",
                    data=pdf_bytes,
                    file_name="Shaft_Design_Data_Sheet.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            else:
                st.error("⚠️ Topology Error: Supports must be separated (Span > 0).")
        else:
            # Show empty schematic if analysis not possible
            st.pyplot(fig)
            st.warning("⚠️ TOPOLOGY INCOMPLETE: Please initialize 2 Bearings.")
    else:
        # Show schematic if button not pressed
        st.pyplot(fig)
        st.info("👆 Configure nexus components and click 'ACTIVATE SIMULATION CORE'.")
