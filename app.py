import time
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

from src.aml.reconciliation import ReconciliationService
from src.aml.verifier import AMLVerifier
from src.database.models import AMLResultRecord, TransactionRecord
from src.database.session import db_session
from src.kafka_client.producer import TransactionProducer
from src.models.transaction import Transaction, TransactionType

st.set_page_config(
    page_title="AML Verification Dashboard",
    page_icon="🔍",
    layout="wide",
)

RISK_COLORS = {
    "low": "#22c55e",
    "medium": "#f59e0b",
    "high": "#ef4444",
    "blocked": "#7c3aed",
}

RISK_BG = {
    "low": "#dcfce7",
    "medium": "#fef3c7",
    "high": "#fee2e2",
    "blocked": "#ede9fe",
}


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=5)
def load_aml_results() -> pd.DataFrame:
    with db_session() as session:
        rows = session.execute(
            text("""
                SELECT r.result_id, r.transaction_id, r.account_id,
                       r.risk_level, r.triggered_rules, r.amount_usd,
                       r.verified_at, r.notes
                FROM aml_results r
                ORDER BY r.verified_at DESC
                LIMIT 500
            """)
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=[
        "result_id", "transaction_id", "account_id",
        "risk_level", "triggered_rules", "amount_usd",
        "verified_at", "notes",
    ])
    df["amount_usd"] = df["amount_usd"].astype(float)
    df["verified_at"] = pd.to_datetime(df["verified_at"], utc=True)
    return df


@st.cache_data(ttl=5)
def load_transaction_counts() -> dict:
    with db_session() as session:
        txn_count = session.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
        result_count = session.execute(text("SELECT COUNT(*) FROM aml_results")).scalar()
        suspicious = session.execute(
            text("SELECT COUNT(*) FROM aml_results WHERE risk_level IN ('high', 'blocked')")
        ).scalar()
    return {"transactions": txn_count or 0, "results": result_count or 0, "suspicious": suspicious or 0}


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("AML Service")
    st.caption("Anti-Money Laundering Verification")
    st.divider()

    page = st.radio(
        "Navigation",
        ["Overview", "Transactions", "Analytics", "Reconciliation", "Produce"],
        label_visibility="collapsed",
    )

    st.divider()
    if st.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── Overview ──────────────────────────────────────────────────────────────────

if page == "Overview":
    st.title("Overview")

    counts = load_transaction_counts()
    df = load_aml_results()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Transactions", counts["transactions"])
    col2.metric("Verified", counts["results"])
    col3.metric("Suspicious", counts["suspicious"], delta=None)
    col4.metric(
        "Detection Rate",
        f"{counts['suspicious'] / counts['results'] * 100:.1f}%" if counts["results"] else "—",
    )

    st.divider()

    if df.empty:
        st.info("No transactions in the database yet. Use the **Produce** page to generate some.")
    else:
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Risk Distribution")
            risk_counts = df["risk_level"].value_counts().reset_index()
            risk_counts.columns = ["risk_level", "count"]
            fig = px.pie(
                risk_counts,
                names="risk_level",
                values="count",
                color="risk_level",
                color_discrete_map=RISK_COLORS,
                hole=0.4,
            )
            fig.update_layout(margin=dict(t=0, b=0), height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.subheader("Volume Over Time")
            df_time = df.copy()
            df_time["hour"] = df_time["verified_at"].dt.floor("h")
            volume = df_time.groupby(["hour", "risk_level"]).size().reset_index(name="count")
            fig2 = px.bar(
                volume,
                x="hour",
                y="count",
                color="risk_level",
                color_discrete_map=RISK_COLORS,
            )
            fig2.update_layout(margin=dict(t=0, b=0), height=300, legend_title="Risk")
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Recent Alerts")
        alerts = df[df["risk_level"].isin(["high", "blocked"])].head(10)
        if alerts.empty:
            st.success("No suspicious transactions detected.")
        else:
            for _, row in alerts.iterrows():
                color = RISK_COLORS[row["risk_level"]]
                rules = ", ".join(row["triggered_rules"]) if row["triggered_rules"] else "—"
                st.markdown(
                    f"""<div style="border-left: 4px solid {color}; padding: 8px 12px; margin: 4px 0;
                    background: {RISK_BG[row['risk_level']]}; border-radius: 4px;">
                    <b>{row['account_id']}</b> &nbsp;
                    <span style="color:{color}; font-weight:bold">{row['risk_level'].upper()}</span>
                    &nbsp;·&nbsp; ${row['amount_usd']:,.2f}
                    &nbsp;·&nbsp; rules: {rules}
                    &nbsp;·&nbsp; <small>{row['verified_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}</small>
                    </div>""",
                    unsafe_allow_html=True,
                )


# ── Transactions ──────────────────────────────────────────────────────────────

elif page == "Transactions":
    st.title("Transactions")

    df = load_aml_results()
    if df.empty:
        st.info("No transactions yet.")
    else:
        col1, col2, col3 = st.columns(3)
        risk_filter = col1.multiselect(
            "Risk level",
            options=["low", "medium", "high", "blocked"],
            default=["low", "medium", "high", "blocked"],
        )
        account_filter = col2.text_input("Account ID contains")
        min_amount = col3.number_input("Min amount ($)", value=0.0, step=100.0)

        filtered = df[df["risk_level"].isin(risk_filter)]
        if account_filter:
            filtered = filtered[filtered["account_id"].str.contains(account_filter.upper())]
        if min_amount:
            filtered = filtered[filtered["amount_usd"] >= min_amount]

        st.caption(f"Showing {len(filtered)} of {len(df)} records")

        def style_risk(val):
            color = RISK_COLORS.get(val, "#000")
            bg = RISK_BG.get(val, "#fff")
            return f"color: {color}; background-color: {bg}; font-weight: bold; border-radius: 4px; padding: 2px 6px;"

        display = filtered[["account_id", "risk_level", "amount_usd", "triggered_rules", "verified_at", "notes"]].copy()
        display.columns = ["Account", "Risk", "Amount (USD)", "Triggered Rules", "Verified At", "Notes"]
        display["Amount (USD)"] = display["Amount (USD)"].map("${:,.2f}".format)
        display["Triggered Rules"] = display["Triggered Rules"].apply(
            lambda r: ", ".join(r) if r else "—"
        )
        display["Verified At"] = display["Verified At"].dt.strftime("%Y-%m-%d %H:%M:%S")

        st.dataframe(
            display.style.map(style_risk, subset=["Risk"]),
            use_container_width=True,
            height=500,
        )


# ── Analytics ─────────────────────────────────────────────────────────────────

elif page == "Analytics":
    st.title("Analytics")

    df = load_aml_results()
    if df.empty:
        st.info("No data to analyse yet.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Top Accounts by Transaction Count")
            top_accounts = df["account_id"].value_counts().head(10).reset_index()
            top_accounts.columns = ["account_id", "count"]
            fig = px.bar(top_accounts, x="count", y="account_id", orientation="h",
                         color_discrete_sequence=["#3b82f6"])
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=350)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Amount Distribution by Risk Level")
            fig2 = px.box(
                df,
                x="risk_level",
                y="amount_usd",
                color="risk_level",
                color_discrete_map=RISK_COLORS,
                category_orders={"risk_level": ["low", "medium", "high", "blocked"]},
            )
            fig2.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Triggered Rules Frequency")
        all_rules: list[str] = []
        for rules in df["triggered_rules"]:
            if rules:
                all_rules.extend(rules)
        if all_rules:
            rule_counts = pd.Series(all_rules).value_counts().reset_index()
            rule_counts.columns = ["rule", "count"]
            fig3 = px.bar(rule_counts, x="rule", y="count", color_discrete_sequence=["#8b5cf6"])
            fig3.update_layout(height=280)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.success("No rules triggered — all transactions are clean.")

        st.subheader("Cumulative Suspicious Transactions")
        suspicious = df[df["risk_level"].isin(["high", "blocked"])].sort_values("verified_at")
        if not suspicious.empty:
            suspicious = suspicious.copy()
            suspicious["cumulative"] = range(1, len(suspicious) + 1)
            fig4 = px.line(suspicious, x="verified_at", y="cumulative",
                           color_discrete_sequence=["#ef4444"])
            fig4.update_layout(height=250)
            st.plotly_chart(fig4, use_container_width=True)


# ── Reconciliation ────────────────────────────────────────────────────────────

elif page == "Reconciliation":
    st.title("Reconciliation")
    st.caption("Compares Kafka high-watermark offsets against PostgreSQL row counts to detect data loss or unprocessed messages.")

    if st.button("Run Reconciliation", type="primary"):
        with st.spinner("Checking Kafka vs database..."):
            try:
                report = ReconciliationService().run()

                col1, col2, col3 = st.columns(3)
                col1.metric("Kafka Messages", report.kafka_total_messages)
                col2.metric("DB Transactions", report.db_transaction_count,
                            delta=report.db_transaction_count - report.kafka_total_messages or None)
                col3.metric("DB Results", report.db_result_count)

                st.divider()

                if report.is_healthy:
                    st.success("Reconciliation passed — Kafka and database are in sync.")
                else:
                    if report.missing_in_db > 0:
                        st.error(f"{report.missing_in_db} messages produced to Kafka but missing from DB.")
                    if report.unverified_in_db > 0:
                        st.warning(f"{report.unverified_in_db} transactions in DB have no AML result yet.")
                    if report.duplicate_result_ids:
                        st.error(f"Duplicate AML results for {len(report.duplicate_result_ids)} transaction(s):")
                        st.code("\n".join(report.duplicate_result_ids))

            except Exception as exc:
                st.error(f"Reconciliation failed: {exc}")


# ── Produce ───────────────────────────────────────────────────────────────────

elif page == "Produce":
    st.title("Produce Test Transactions")
    st.caption("Send synthetic transactions directly to Kafka to test the pipeline.")

    tab1, tab2 = st.tabs(["Bulk Generate", "Manual Transaction"])

    with tab1:
        count = st.slider("Number of transactions", 1, 100, 10)
        include_suspicious = st.checkbox("Include suspicious transactions (high-value + blacklisted)", value=True)

        if st.button("Produce", type="primary"):
            produced = 0
            types = list(TransactionType)
            with st.spinner(f"Producing {count} transactions..."):
                try:
                    with TransactionProducer() as producer:
                        for i in range(count):
                            amount = Decimal(str(100 + (i * 97) % 15000))
                            counterparty = f"ACCT{(i + 1):06d}"

                            if include_suspicious and i == count // 2:
                                amount = Decimal("15000.00")
                            if include_suspicious and i == count - 1:
                                counterparty = "SANCTIONED001"

                            txn = Transaction(
                                account_id=f"ACCT{i:06d}",
                                counterparty_account_id=counterparty,
                                amount_usd=amount,
                                transaction_type=types[i % len(types)],
                                timestamp=datetime.now(timezone.utc),
                            )
                            producer.send_transaction(txn)
                            produced += 1
                    st.success(f"Produced {produced} transactions to `aml.transactions`.")
                    st.info("Run `python main.py verify` in the terminal to process them, then refresh.")
                except Exception as exc:
                    st.error(f"Failed: {exc}")

    with tab2:
        with st.form("manual_txn"):
            c1, c2 = st.columns(2)
            account_id = c1.text_input("Account ID", value="ACCT100001")
            counterparty_id = c2.text_input("Counterparty Account ID", value="ACCT200001")
            amount = st.number_input("Amount (USD)", value=500.00, min_value=0.01, step=100.0)
            txn_type = st.selectbox("Transaction Type", [t.value for t in TransactionType])

            submitted = st.form_submit_button("Send to Kafka", type="primary")
            if submitted:
                try:
                    txn = Transaction(
                        account_id=account_id,
                        counterparty_account_id=counterparty_id,
                        amount_usd=Decimal(str(amount)),
                        transaction_type=TransactionType(txn_type),
                        timestamp=datetime.now(timezone.utc),
                    )
                    with TransactionProducer() as producer:
                        producer.send_transaction(txn)
                    st.success(f"Transaction `{txn.transaction_id}` sent.")
                    if amount >= 10000:
                        st.warning("Amount >= $10,000 — this will trigger the **amount_threshold** rule.")
                    if counterparty_id.upper() in ("SANCTIONED001", "OFAC_BLOCKED_002", "TERROR_FINANCE_003"):
                        st.error("Counterparty is on the blacklist — this will be **BLOCKED**.")
                except Exception as exc:
                    st.error(f"Failed: {exc}")
