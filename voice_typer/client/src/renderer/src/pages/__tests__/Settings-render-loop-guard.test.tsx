import { makeConfig } from "@/__tests__/helpers/fixtures";
import {
	type GuardCommand,
	renderLoopGuard,
} from "@/__tests__/helpers/renderLoopGuard";

const commands: GuardCommand[] = [
	// get_config fires twice on mount: once from
	// useSettingsConfig.loadConfig and once from the useTheme singleton
	// reload (themeInitStarted initOnce guard).
	{ name: "get_config", response: makeConfig({}), expected: 2 },
	// KeyboardPermissionBanner's mount probe, granted, so the banner
	// stays hidden.
	{
		name: "onboarding_check_permissions",
		response: {
			platform: "windows",
			state: "granted",
			needed: false,
			instructions: null,
		},
	},
];

renderLoopGuard({
	id: "settings",
	page: () => import("@/pages/Settings"),
	// The whole renderer suite loads this page late under a saturated
	// worker pool; 5s is the helper default and flaked in the full run.
	timeoutMs: 15_000,
	commands,
	// The page renders its chrome (title) immediately; the
	// load-completion signal is the exactly-once counter assertion.
	settle: (s) => s.getByText("Settings") != null,
});
