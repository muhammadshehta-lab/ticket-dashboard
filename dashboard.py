# أ. تحديد مصفوفة الترتيب المنطقي المتتالي للفترات الزمنية والفئات الرئيسية
time_order = ["Under 15 Mins", "15-30 Mins", "30-45 Mins", "45-60 Mins", "Over 1 Hour"]
category_order = ["Response Time", "Service Resolution"]

if not df_metrics.empty:
    # (بناء البيانات وتجميعها كما في تطبيقك)
    df_metrics["Response Tier"] = df_metrics["Response Take (min)"].apply(assign_time_tier)
    df_metrics["Service Tier"] = df_metrics["Request Take (min)"].apply(assign_time_tier)
    
    r_data = df_metrics.groupby("Response Tier").size().reset_index(name="Tickets")
    r_data["SLA Category"] = "Response Time"
    r_data.rename(columns={"Response Tier": "SLA Tier"}, inplace=True)
    
    s_data = df_metrics.groupby("Service Tier").size().reset_index(name="Tickets")
    s_data["SLA Category"] = "Service Resolution"
    s_data.rename(columns={"Service Tier": "SLA Tier"}, inplace=True)
    
    sunburst_df = pd.concat([r_data, s_data], ignore_index=True)
    
    # ب. تحويل الأعمدة إلى نوع Categorical مخصص وإجبار الترتيب البرمجي قبل الرسم
    sunburst_df["SLA Category"] = pd.Categorical(sunburst_df["SLA Category"], categories=category_order, ordered=True)
    sunburst_df["SLA Tier"] = pd.Categorical(sunburst_df["SLA Tier"], categories=time_order, ordered=True)
    
    # ج. فرز إطار البيانات بناءً على الترتيب الفئوي الجديد لضمان تسلسل الإدخال للرسم
    sunburst_df = sunburst_df.sort_values(["SLA Category", "SLA Tier"]).reset_index(drop=True)
    
    # د. بناء المخطط مع الحفاظ على الألوان المحددة لكل فئة زمنية ثابتة
    fig_sunburst = px.sunburst(
        sunburst_df, 
        path=["SLA Category", "SLA Tier"], 
        values="Tickets", 
        color="SLA Tier",
        color_discrete_map={
            "Under 15 Mins": "#2ea44f", # الأخضر
            "15-30 Mins": "#2188ff",    # الأزرق
            "30-45 Mins": "#bc8cff",    # البنفسجي
            "45-60 Mins": "#f9c513",    # الأصفر
            "Over 1 Hour": "#ea4a5a"    # الأحمر
        }, 
        branchvalues="total"
    )
    
    # هـ. الحطوة السحرية: إيقاف الترتيب التلقائي القائم على القيمة الكبرى (المسبب للمشكلة)
    fig_sunburst.update_traces(
        sort=False,  # تعطيل إعادة الترتيب التلقائي لـ Plotly بناءً على حجم الشريحة
        textinfo="label+percent parent", 
        hovertemplate="<b>%{label}</b><br>Tickets: %{value:,}<br>Percentage: %{percentParent:.1%}"
    )
    
    # و. فرض مصفوفة الترتيب المخصص في هيكل الـ layout العام
    fig_sunburst.update_layout(
        **THEME, 
        height=520,
        categoryorders={
            "SLA Category": category_order,
            "SLA Tier": time_order
        }
    )
    
    st.plotly_chart(fig_sunburst, use_container_width=True)
