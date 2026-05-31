# 1. تحديد الترتيب الزمني المتتالي المتقارب للفئات بشكل صارم ومسبق
time_order = ["Under 15 Mins", "15-30 Mins", "30-45 Mins", "45-60 Mins", "Over 1 Hour"]
category_order = ["Response Time", "Service Resolution"]

if not df_metrics.empty:
    df_metrics["Response Tier"] = df_metrics["Response Take (min)"].apply(assign_time_tier)
    df_metrics["Service Tier"] = df_metrics["Request Take (min)"].apply(assign_time_tier)
    
    r_data = df_metrics.groupby("Response Tier").size().reset_index(name="Tickets")
    r_data["SLA Category"] = "Response Time"
    r_data.rename(columns={"Response Tier": "SLA Tier"}, inplace=True)
    
    s_data = df_metrics.groupby("Service Tier").size().reset_index(name="Tickets")
    s_data["SLA Category"] = "Service Resolution"
    s_data.rename(columns={"Service Tier": "SLA Tier"}, inplace=True)
    
    sunburst_df = pd.concat([r_data, s_data], ignore_index=True)
    
    # تحويل العمود إلى فئة تتبع الترتيب المحدد (Categorical) لمنع بعثرة البيانات
    sunburst_df["SLA Tier"] = pd.Categorical(sunburst_df["SLA Tier"], categories=time_order, ordered=True)
    sunburst_df["SLA Category"] = pd.Categorical(sunburst_df["SLA Category"], categories=category_order, ordered=True)
    
    # فرز الإطار البرمجي بناءً على الترتيب الفئوي الجديد قبل الرسم
    sunburst_df = sunburst_df.sort_values(["SLA Category", "SLA Tier"]).reset_index(drop=True)
    
    fig_sunburst = px.sunburst(
        sunburst_df, 
        path=["SLA Category", "SLA Tier"], 
        values="Tickets", 
        color="SLA Tier",
        color_discrete_map={
            "Under 15 Mins": "#2ea44f", 
            "15-30 Mins": "#2188ff", 
            "30-45 Mins": "#bc8cff", 
            "45-60 Mins": "#f9c513", 
            "Over 1 Hour": "#ea4a5a"
        }, 
        branchvalues="total"
    )
    
    # إجبار الترتيب وإلغاء ميزة الترتيب بحسب القيمة التلقائية لـ Plotly
    fig_sunburst.update_traces(
        sort=False,  # تعطيل الترتيب التلقائي المبني على النسبة المئوية الكبرى
        textinfo="label+percent parent", 
        hovertemplate="<b>%{label}</b><br>Tickets: %{value:,}<br>Percentage: %{percentParent:.1%}"
    )
    
    # تطبيق مصفوفة الترتيب المخصص في الـ layout لضمان ثبات الرسم
    fig_sunburst.update_layout(
        **THEME, 
        height=520,
        categoryorders={
            "SLA Category": category_order,
            "SLA Tier": time_order
        }
    )
    
    st.plotly_chart(fig_sunburst, use_container_width=True)
