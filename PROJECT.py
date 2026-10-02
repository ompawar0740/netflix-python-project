from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


DATA_PATH = Path(__file__).with_name("Netflix.csv")
ICON_PATH = Path(__file__).with_name("icon-square.png")
CHART_COLORS = ["#E50914", "#292929", "#B20710", "#777777", "#FF646D"]
WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

st.set_page_config(
	page_title="Netflix viewing insights",
	page_icon=str(ICON_PATH),
	layout="wide",
)
st.logo(str(ICON_PATH), size="large")


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
	data = pd.read_csv(path)
	data["Watch_Date"] = pd.to_datetime(data["Watch_Date"], errors="coerce")
	return data


def format_number(value: float) -> str:
	return f"{value:,.0f}"


def horizontal_bar(
	data: pd.DataFrame,
	label: str,
	value: str,
	color: str,
	value_title: str,
) -> alt.Chart:
	return (
		alt.Chart(data)
		.mark_bar(color=color, cornerRadiusEnd=4, size=22)
		.encode(
			x=alt.X(
				f"{value}:Q",
				title=value_title,
				axis=alt.Axis(format="~s", grid=True),
			),
			y=alt.Y(f"{label}:N", title=None, sort="-x"),
			tooltip=[
				alt.Tooltip(f"{label}:N", title=label.replace("_", " ")),
				alt.Tooltip(f"{value}:Q", title=value_title, format=",.1f"),
			],
		)
		.properties(height=260)
		.configure_view(strokeOpacity=0)
		.configure_axis(gridColor="#E7E7E7", labelColor="#333333", titleColor="#333333")
	)


def show_chart(title: str, chart: alt.Chart, note: str) -> None:
	with st.container(border=True):
		st.subheader(title)
		st.altair_chart(chart, width="stretch")
		st.caption(note)


if not DATA_PATH.exists():
	st.error(f"Dataset not found: {DATA_PATH.name}. Place it beside PROJECT.py and reload the app.")
	st.stop()

try:
	netflix = load_data(str(DATA_PATH))
except (OSError, pd.errors.ParserError, KeyError) as error:
	st.error(f"Could not load the Netflix dataset: {error}")
	st.stop()

required_columns = {
	"Customer_ID",
	"Region",
	"Subscription_Plan",
	"Title",
	"Category",
	"Type",
	"Rating",
	"Watch_Count",
	"Watch_Date",
	"Watch_Time_Minutes",
	"Device",
	"Monthly_Revenue",
}
missing_columns = required_columns.difference(netflix.columns)
if missing_columns:
	st.error(f"Dataset is missing required columns: {', '.join(sorted(missing_columns))}")
	st.stop()

netflix = netflix.dropna(subset=["Watch_Date"]).copy()
netflix["Weekday"] = netflix["Watch_Date"].dt.day_name()
netflix["Month"] = netflix["Watch_Date"].dt.to_period("M").dt.to_timestamp()

title_icon, title_text = st.columns([1.3, 10], vertical_alignment="center")
with title_icon:
	st.image(str(ICON_PATH), width=96)
with title_text:
	st.title(":red[Netflix] viewing insights")
st.caption("A closer look at audience activity, content performance, and recorded revenue.")

with st.sidebar:
	st.header("Filter the dataset", icon=":material/filter_list:")
	min_date = netflix["Watch_Date"].min().date()
	max_date = netflix["Watch_Date"].max().date()
	date_range = st.date_input(
		"Watch date range",
		value=(min_date, max_date),
		min_value=min_date,
		max_value=max_date,
	)
	regions = st.multiselect("Region", sorted(netflix["Region"].dropna().unique()), default=sorted(netflix["Region"].dropna().unique()))
	plans = st.multiselect(
		"Subscription plan",
		sorted(netflix["Subscription_Plan"].dropna().unique()),
		default=sorted(netflix["Subscription_Plan"].dropna().unique()),
	)
	categories = st.multiselect(
		"Category",
		sorted(netflix["Category"].dropna().unique()),
		default=sorted(netflix["Category"].dropna().unique()),
	)

filtered = netflix[
	netflix["Region"].isin(regions)
	& netflix["Subscription_Plan"].isin(plans)
	& netflix["Category"].isin(categories)
]
if len(date_range) == 2:
	start_date, end_date = date_range
	filtered = filtered[
		filtered["Watch_Date"].dt.date.between(start_date, end_date)
	]

if filtered.empty:
	st.info("No records match these filters. Adjust the selections in the sidebar.")
	st.stop()

total_revenue = filtered["Monthly_Revenue"].sum()
unique_customers = filtered["Customer_ID"].nunique()
average_rating = filtered["Rating"].mean()
watch_hours = filtered["Watch_Time_Minutes"].sum() / 60

metric_columns = st.columns(4)
metric_columns[0].metric("Recorded revenue", format_number(total_revenue), border=True)
metric_columns[1].metric("Customers", f"{unique_customers:,}", border=True)
metric_columns[2].metric("Average rating", f"{average_rating:.1f} / 5", border=True)
metric_columns[3].metric("Watch time", f"{watch_hours:,.0f} hrs", border=True)

st.header("Revenue signals", icon=":material/monitoring:")
region_data = (
	filtered.groupby("Region", as_index=False)["Monthly_Revenue"]
	.sum()
	.rename(columns={"Monthly_Revenue": "revenue"})
)
monthly_data = (
	filtered.groupby("Month", as_index=False)["Monthly_Revenue"]
	.sum()
	.rename(columns={"Monthly_Revenue": "revenue"})
)
category_data = (
	filtered.groupby("Category", as_index=False)["Monthly_Revenue"]
	.sum()
	.rename(columns={"Monthly_Revenue": "revenue", "Category": "category"})
)
plan_revenue = (
	filtered.groupby("Subscription_Plan", as_index=False)["Monthly_Revenue"]
	.sum()
	.rename(columns={"Subscription_Plan": "plan", "Monthly_Revenue": "revenue"})
)
plan_revenue["share"] = plan_revenue["revenue"] / plan_revenue["revenue"].sum()

revenue_row = st.columns(2)
with revenue_row[0]:
	show_chart(
		"Revenue by region",
		horizontal_bar(region_data, "Region", "revenue", CHART_COLORS[0], "Revenue"),
		"Sum of Monthly_Revenue for the filtered records.",
	)
with revenue_row[1]:
	monthly_chart = (
		alt.Chart(monthly_data)
		.mark_area(color=CHART_COLORS[0], opacity=0.18, line={"color": CHART_COLORS[0], "strokeWidth": 3})
		.encode(
			x=alt.X("Month:T", title="Watch month", axis=alt.Axis(format="%b %Y", labelAngle=0)),
			y=alt.Y("revenue:Q", title="Revenue", axis=alt.Axis(format="~s", grid=True)),
			tooltip=[alt.Tooltip("Month:T", title="Watch month", format="%B %Y"), alt.Tooltip("revenue:Q", title="Revenue", format=",.0f")],
		)
		.properties(height=260)
		.configure_view(strokeOpacity=0)
		.configure_axis(gridColor="#E7E7E7", labelColor="#333333", titleColor="#333333")
	)
	show_chart("Revenue by watch month", monthly_chart, "Revenue grouped by the month each record was watched.")

category_chart = horizontal_bar(category_data, "category", "revenue", CHART_COLORS[2], "Revenue")
plan_chart = (
	alt.Chart(plan_revenue)
	.mark_arc(innerRadius=68, outerRadius=112, stroke="#FFFFFF", strokeWidth=2)
	.encode(
		theta=alt.Theta("revenue:Q", title="Revenue"),
		color=alt.Color("plan:N", title="Plan", scale=alt.Scale(range=CHART_COLORS)),
		tooltip=[
			alt.Tooltip("plan:N", title="Subscription plan"),
			alt.Tooltip("revenue:Q", title="Revenue", format=",.0f"),
			alt.Tooltip("share:Q", title="Share", format=".1%"),
		],
	)
	.properties(height=260)
)
revenue_mix = st.columns(2)
with revenue_mix[0]:
	show_chart("Revenue by category", category_chart, "Categories ranked by recorded revenue.")
with revenue_mix[1]:
	show_chart("Revenue mix by plan", plan_chart, "Share of filtered recorded revenue for each subscription plan.")

st.header("Audience and engagement", icon=":material/groups:")
plan_ratings = (
	filtered.groupby("Subscription_Plan", as_index=False)
	.agg(average_rating=("Rating", "mean"), records=("Customer_ID", "size"))
)
plan_rating_chart = (
	alt.Chart(plan_ratings)
	.mark_bar(cornerRadiusEnd=4, size=30)
	.encode(
		x=alt.X("average_rating:Q", title="Average rating", scale=alt.Scale(domain=[0, 5]), axis=alt.Axis(grid=True)),
		y=alt.Y("Subscription_Plan:N", title=None, sort=["Basic", "Standard", "Premium"]),
		color=alt.Color("Subscription_Plan:N", title="Plan", scale=alt.Scale(range=CHART_COLORS)),
		tooltip=[alt.Tooltip("Subscription_Plan:N", title="Subscription plan"), alt.Tooltip("average_rating:Q", title="Average rating", format=".2f"), alt.Tooltip("records:Q", title="Records")],
	)
	.properties(height=230)
	.configure_view(strokeOpacity=0)
	.configure_axis(gridColor="#E7E7E7", labelColor="#333333", titleColor="#333333")
)

weekday_data = (
	filtered.groupby("Weekday", as_index=False)["Monthly_Revenue"]
	.sum()
	.rename(columns={"Monthly_Revenue": "revenue"})
)
weekday_chart = (
	alt.Chart(weekday_data)
	.mark_bar(color=CHART_COLORS[3], cornerRadiusEnd=4, size=23)
	.encode(
		x=alt.X("Weekday:N", title=None, sort=WEEKDAY_ORDER, axis=alt.Axis(labelAngle=-25)),
		y=alt.Y("revenue:Q", title="Revenue", axis=alt.Axis(format="~s", grid=True)),
		tooltip=[alt.Tooltip("Weekday:N", title="Day"), alt.Tooltip("revenue:Q", title="Revenue", format=",.0f")],
	)
	.properties(height=260)
	.configure_view(strokeOpacity=0)
	.configure_axis(gridColor="#E7E7E7", labelColor="#333333", titleColor="#333333")
)

top_titles = (
	filtered.groupby("Title", as_index=False)["Watch_Count"]
	.sum()
	.nlargest(8, "Watch_Count")
	.rename(columns={"Watch_Count": "watches", "Title": "title"})
)
titles_chart = horizontal_bar(top_titles, "title", "watches", CHART_COLORS[4], "Recorded watches")

engagement_row = st.columns(2)
with engagement_row[0]:
	show_chart("Average rating by plan", plan_rating_chart, "Average customer rating on a 1-5 scale; hover for record counts.")
with engagement_row[1]:
	show_chart("Revenue by weekday", weekday_chart, "Weekdays are shown in calendar order, not ranked by revenue.")

with st.container(border=True):
	st.subheader("Most-watched titles")
	st.altair_chart(titles_chart, width="stretch")
	st.caption("Top eight titles by the sum of Watch_Count in the filtered records.")

with st.expander("Explore records and data quality", icon=":material/table_view:"):
	st.caption(f"Showing {len(filtered):,} of {len(netflix):,} records. Source: {DATA_PATH.name}")
	display_columns = [
		"Customer_ID", "Region", "Subscription_Plan", "Title", "Category", "Type",
		"Rating", "Watch_Count", "Watch_Date", "Watch_Time_Minutes", "Device", "Monthly_Revenue",
	]
	st.dataframe(filtered[display_columns].sort_values("Watch_Date", ascending=False), hide_index=True)
	quality_columns = st.columns(3)
	quality_columns[0].metric("Source rows", f"{len(netflix):,}")
	quality_columns[1].metric("Duplicate rows", f"{int(netflix.duplicated().sum()):,}")
	quality_columns[2].metric("Missing cells", f"{int(netflix.isna().sum().sum()):,}")













