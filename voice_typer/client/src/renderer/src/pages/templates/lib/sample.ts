// Measured-skeleton sample for the Templates page.
// Typical trigger lines with a match-mode pill and a single
// truncated expansion, matching the row height the page renders.
import type { TemplateRow } from "./types";

export const SAMPLE_TEMPLATE_ROWS: TemplateRow[] = [
	{
		index: 0,
		id: "sample-template-0",
		trigger: "sign off",
		expansion: "Thanks for your time, see you tomorrow.",
		match_mode: "exact",
		variables: 0,
		used_variables: [],
	},
	{
		index: 1,
		id: "sample-template-1",
		trigger: "meeting notes",
		expansion: "Notes from today's meeting are ready to review.",
		match_mode: "contains",
		variables: 1,
		used_variables: ["{today}"],
	},
	{
		index: 2,
		id: "sample-template-2",
		trigger: "follow up",
		expansion: "Following up on your message from earlier today.",
		match_mode: "exact",
		variables: 0,
		used_variables: [],
	},
	{
		index: 3,
		id: "sample-template-3",
		trigger: "my address",
		expansion: "123 Main Street, Springfield, IL 62701",
		match_mode: "contains",
		variables: 0,
		used_variables: [],
	},
	{
		index: 4,
		id: "sample-template-4",
		trigger: "quote for project",
		expansion: "Our estimate will be ready by {today} for review.",
		match_mode: "exact",
		variables: 1,
		used_variables: ["{today}"],
	},
	{
		index: 5,
		id: "sample-template-5",
		trigger: "out of office",
		expansion: "I am out of the office until further notice.",
		match_mode: "contains",
		variables: 0,
		used_variables: [],
	},
	{
		index: 6,
		id: "sample-template-6",
		trigger: "schedule call",
		expansion: "Let's schedule a call for later this week.",
		match_mode: "exact",
		variables: 0,
		used_variables: [],
	},
	{
		index: 7,
		id: "sample-template-7",
		trigger: "copy citation",
		expansion: "Copied from clipboard: {clipboard}",
		match_mode: "contains",
		variables: 1,
		used_variables: ["{clipboard}"],
	},
];
