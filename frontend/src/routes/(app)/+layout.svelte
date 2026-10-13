<script lang="ts">
	import { run } from 'svelte/legacy';

	// Most of your app wide CSS should be put in this file
	import '../../app.css';

	import { safeTranslate, setUseRiskCategoryLabel } from '$lib/utils/i18n';

	import SideBar from '$lib/components/SideBar/SideBar.svelte';
	import Breadcrumbs from '$lib/components/Breadcrumbs/Breadcrumbs.svelte';
	import {
		pageTitle,
		modelName,
		modelDescription,
		clientSideToast,
		getStartedTrigger
	} from '$lib/utils/stores';
	import { getCookie, deleteCookie } from '$lib/utils/cookies';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { m } from '$paraglide/messages';

	import type { LayoutData, ActionData } from './$types';
	import { getSidebarVisibleItems } from '$lib/utils/sidebar-config';
	import { getModalStore, type ModalStore } from '$lib/components/Modals/stores';

	import CommandPalette from '$lib/components/CommandPalette/CommandPalette.svelte';
	import ThemeToggle from '$lib/components/ThemeToggle/ThemeToggle.svelte';
	import NotificationBell from '$lib/components/NotificationBell/NotificationBell.svelte';
	import ChatWidget from '$lib/components/ChatWidget/ChatWidget.svelte';
	import {
		interceptExternalLinks,
		setGlobalModalStore,
		setShowWarningExternalLinks
	} from '$lib/utils/external-links';
	import { onMount } from 'svelte';
	import { initThemeFromUser } from '$lib/utils/theme';

	const isMac = browser && navigator.platform.toUpperCase().indexOf('MAC') >= 0;
	const modifierKey = isMac ? '⌘' : 'Ctrl';

	let commandPalette: ReturnType<typeof CommandPalette> | undefined = $state();

	let sidebarOpen = $state(true);

	let classesSidebarOpen = $derived((open: boolean) => (open ? 'ml-64' : 'ml-7'));

	interface Props {
		data: LayoutData;
		form: ActionData;
		sideBarVisibleItems?: any;
		children?: import('svelte').Snippet;
	}

	let {
		data,
		form,
		sideBarVisibleItems = getSidebarVisibleItems(data?.featureflags),
		children
	}: Props = $props();

	const modalStore: ModalStore = getModalStore();

	// Sync the qualification/risk-category wording flag before children render
	// (hydration would otherwise flip labels back), then keep it in sync when
	// settings are invalidated.
	setUseRiskCategoryLabel(data?.settings?.use_risk_category_label);
	$effect.pre(() => {
		setUseRiskCategoryLabel(data?.settings?.use_risk_category_label);
	});

	// Display title, model name, and description from either page data or manual store setting
	const displayTitle = $derived($page.data?.title || $pageTitle);

	// Auto-detect model from URL for list pages
	// Match pattern: /model-name or /model-name/ (but not /model-name/uuid or /model-name/something)
	const urlModel = $derived(() => {
		const path = $page.url.pathname;
		const match = path.match(/^\/([a-z-]+)\/?$/);
		return match ? match[1] : null;
	});

	// Generate description key from URL model: "risk-matrices" → "riskMatricesDescription"
	const urlDescriptionKey = $derived(() => {
		const model = urlModel();
		if (!model) return null;

		const camelCase = model
			.split('-')
			.map((word, index) => (index === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1)))
			.join('');
		return `${camelCase}Description`;
	});

	// Determine if we're on a list page vs detail page
	// List page: URL matches /model-name pattern (e.g., /risk-assessments)
	// Detail page: has an object title from loadDetail (e.g., /risk-assessments/uuid)
	const matchesListUrl = $derived(!!urlModel());
	const hasObjectTitle = $derived(!!$page.data?.title);

	// For list pages: show description subtitle
	// For detail pages: show model name subtitle
	const displayModelName = $derived(
		hasObjectTitle ? $page.data?.modelVerboseName || $modelName : ''
	);

	const displayModelDescription = $derived(
		(() => {
			// Only show description on list pages (not on detail pages with object titles)
			// Exception: pages that explicitly provide a modelDescriptionKey
			if (hasObjectTitle && !$page.data?.modelDescriptionKey) return '';
			if (!matchesListUrl && !$page.data?.modelDescriptionKey) return '';

			// List pages: get description from i18n
			const descKey = $page.data?.modelDescriptionKey || urlDescriptionKey();
			if (descKey && m[descKey]) {
				return m[descKey]();
			}

			// Fallback to manual store
			return $modelDescription;
		})()
	);

	// Initialize external link interceptor
	$effect(() => {
		if (browser) {
			setGlobalModalStore(modalStore);
			// Set the warning preference from settings (default to true if not set)
			const showWarning = data?.settings?.show_warning_external_links ?? true;
			setShowWarningExternalLinks(showWarning);
			interceptExternalLinks();
		}
	});

	// Apply the theme persisted in the user's server-side preferences (ui.theme).
	// Falls back to localStorage / system preference when no server value is set.
	onMount(() => {
		initThemeFromUser(data.user?.preferences);
	});

	// Handle login-specific logic
	run(() => {
		if (browser) {
			const fromLogin = getCookie('from_login');
			if (fromLogin === 'true') {
				deleteCookie('from_login');
				fetch('/fe-api/waiting-risk-acceptances').then(async (res) => {
					const data = await res.json();
					const number = data.count ?? 0;
					if (number <= 0) return;
				});
			}
		}
	});

	// $inspect(data);
</script>

<svelte:head>
	<title>10A GRC Lab | {safeTranslate(displayTitle)}</title>
</svelte:head>

<!-- App Shell -->
<!-- min-height and background live here (not on <main>) so appbar + main can
     add up to exactly one viewport; min-h-screen on <main> alone always overflowed. -->
<div class="overflow-x-clip min-h-dvh workspace-canvas">
	<SideBar bind:open={sidebarOpen} {sideBarVisibleItems} />
	<header
		class="sticky top-0 z-50 flex h-16 items-center justify-between gap-4 border-b border-surface-200-800 bg-surface-50-950/95 backdrop-blur px-4 sm:px-6 transition-all duration-300 {classesSidebarOpen(
			sidebarOpen
		)}"
	>
		<div class="min-w-0 flex-1">
			<Breadcrumbs />
		</div>
		<div class="flex shrink-0 items-center gap-2">
			{#if sideBarVisibleItems.notifications && !data?.user?.is_third_party}
				<NotificationBell />
			{/if}
			<ThemeToggle />
			{#if data?.featureflags?.custom_portals && !data?.user?.is_third_party}
				<a
					href="/portal"
					class="flex h-9 items-center gap-2 shrink-0 rounded-md border border-surface-200-800 bg-surface-50-950 px-3
		text-[13px] font-medium text-surface-600-400 hover:bg-surface-100-900 hover:text-surface-950-50 transition-colors"
				>
					<i class="fa-solid fa-table-cells-large text-xs" aria-hidden="true"></i>
					<span class="hidden sm:inline">{m.portals()}</span>
				</a>
			{/if}
			{#if !data?.user?.is_third_party}
				<button
					onclick={() => commandPalette?.toggle()}
					aria-label={m.search()}
					data-testid="command-palette-trigger"
					class="flex h-9 items-center gap-2 shrink-0 rounded-md border border-surface-200-800 bg-surface-50-950 px-3
		text-[13px] text-surface-600-400 hover:bg-surface-100-900 hover:text-surface-950-50 transition-colors cursor-pointer"
				>
					<i class="fa-solid fa-magnifying-glass text-xs" aria-hidden="true"></i>
					<span class="hidden sm:inline">{m.searchEllipsis()}</span>
					<kbd
						class="hidden sm:inline-flex items-center rounded border border-surface-200-800 bg-surface-100-900 px-1.5 py-0.5
			font-mono text-[10px] text-surface-500">{modifierKey}K</kbd
					>
				</button>
			{/if}
			{#if data?.user?.is_admin && data?.settings?.show_get_started !== false}
				<button
					onclick={() => getStartedTrigger.set(true)}
					class="flex h-9 shrink-0 items-center gap-2 rounded-md bg-primary-500 px-3 text-[13px] font-semibold text-white
		hover:bg-primary-600 transition-colors cursor-pointer"
				>
					<i class="fa-solid fa-rocket text-xs" aria-hidden="true"></i>
					{m.getStarted()}
				</button>
			{/if}
		</div>
	</header>
	<!-- Router Slot -->
	{#if !data?.user?.is_third_party}
		<CommandPalette bind:this={commandPalette} />
	{/if}
	{#if $page.data.featureflags?.chat_mode}
		<ChatWidget />
	{/if}
	<main class="transition-all duration-300 {classesSidebarOpen(sidebarOpen)}">
		<div class="workspace-page mx-auto">
			{#if displayTitle}
				<header class="mb-6 border-b border-surface-200-800 pb-6 sm:mb-8 sm:pb-8">
					{#if displayModelName}
						<p class="eyebrow mb-2">{safeTranslate(displayModelName)}</p>
					{/if}
					<h1
						class="text-4xl font-medium tracking-[-0.035em] text-surface-950-50 sm:text-5xl"
						id="page-title"
					>
						{safeTranslate(displayTitle)}
					</h1>
					{#if displayModelDescription}
						<p class="mt-2 max-w-2xl text-sm leading-6 text-surface-600-400">
							{safeTranslate(displayModelDescription)}
						</p>
					{/if}
				</header>
			{/if}
			{@render children?.()}
		</div>
	</main>
	<!-- ---- / ---- -->
</div>
