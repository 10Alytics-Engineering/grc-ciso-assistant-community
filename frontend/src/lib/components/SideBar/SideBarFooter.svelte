<script lang="ts">
	import { page } from '$app/state';
	import { breadcrumbs } from '$lib/utils/breadcrumbs';
	import { LOCALE_MAP, language, defaultLangLabels } from '$lib/utils/locales';
	import { m } from '$paraglide/messages';
	import { getLocale, locales, setLocale } from '$paraglide/runtime';

	import { getModalStore, type ModalSettings } from '$lib/components/Modals/stores';
	import { createEventDispatcher, onMount } from 'svelte';
	const dispatch = createEventDispatcher();

	const modalStore = getModalStore();

	let value = $state(getLocale());
	async function handleLocaleChange(event: Event) {
		value = event?.target?.value;
		await fetch('/fe-api/user-preferences', {
			method: 'PATCH',
			body: JSON.stringify({
				lang: value
			})
		}).then(() => setLocale(value));
	}

	async function modalBuildInfo() {
		const res = await fetch('/fe-api/build').then((res) => res.json());
		const modal: ModalSettings = {
			type: 'component',
			component: 'displayJSONModal',
			title: m.aboutCiso(),
			body: JSON.stringify(res)
		};
		openState = false;
		modalStore.trigger(modal);
	}

	const user = page.data.user;
	const initials = (
		[user?.first_name, user?.last_name].filter(Boolean).join(' ') ||
		user?.email ||
		'10A'
	)
		.split(/\s|@/)
		.filter(Boolean)
		.map((part: string) => part[0])
		.join('')
		.slice(0, 2)
		.toUpperCase();

	let enableMoreBtn = $state(false);

	onMount(() => {
		enableMoreBtn = true;
	});

	let openState = $state(false);
	let triggerEl: HTMLButtonElement | undefined = $state();
	let menuStyle = $derived.by(() => {
		if (!openState || !triggerEl) return '';
		const rect = triggerEl.getBoundingClientRect();
		const centerX = rect.left + rect.width / 2;
		return `position: fixed; bottom: ${window.innerHeight - rect.top + 8}px; left: ${centerX}px; transform: translateX(-50%);`;
	});
</script>

<div class="shrink-0 border-t border-surface-200-800 p-3">
	<div class="flex flex-row items-center justify-between gap-1">
		<div class="flex min-w-0 flex-1 items-center gap-2 px-1">
			{#if page.data.user}
				<span
					class="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary-50-950 text-[11px] font-semibold text-primary-700-300"
					aria-hidden="true"
				>
					{initials}
				</span>
				<span class="min-w-0">
					<span
						class="block truncate text-xs font-semibold text-surface-950-50"
						data-testid="sidebar-user-name-display"
					>
						{page.data.user.first_name}
						{page.data.user.last_name}
					</span>
					<span
						class="block truncate text-[11px] text-surface-600-400"
						data-testid="sidebar-user-email-display"
					>
						{page.data.user.email}
					</span>
				</span>
			{/if}
		</div>
		{#if enableMoreBtn}
			<div class="relative">
				<button
					bind:this={triggerEl}
					class="btn bg-initial"
					data-testid="sidebar-more-btn"
					aria-label="More options"
					id="sidebar-more-btn"
					onclick={() => (openState = !openState)}
				>
					<i class="fa-solid fa-ellipsis-vertical"></i>
				</button>
				{#if openState}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div
						class="fixed inset-0 z-[999]"
						onclick={() => (openState = false)}
						onkeydown={(e) => e.key === 'Escape' && (openState = false)}
					></div>
					<div
						style={menuStyle}
						class="z-[1000] card whitespace-nowrap bg-surface-50-950 py-2 w-fit shadow-lg space-y-1 rounded-lg"
						data-testid="sidebar-more-panel"
					>
						<a
							href="/my-profile"
							onclick={() => {
								openState = false;
							}}
							class="unstyled cursor-pointer flex items-center gap-2 w-full px-4 py-2.5 text-left text-sm hover:bg-surface-200-800 disabled:text-surface-400-600 text-surface-950-50"
							data-testid="profile-button"
							><i class="fa-solid fa-address-card mr-2"></i>{m.myProfile()}</a
						>
						<select
							{value}
							onchange={handleLocaleChange}
							class="border-y-transparent border-x-surface-100-900 focus:border-y-transparent focus:border-x-surface-100-900 w-full px-4 py-2.5 cursor-pointer block text-sm text-surface-950-50 bg-surface-50-950 focus:ring-0"
							data-testid="language-select"
						>
							{#each locales as lang}
								<option value={lang} selected={lang === getLocale()}>
									{defaultLangLabels[lang]} ({language[LOCALE_MAP[lang].name]})
								</option>
							{/each}
						</select>
						{#if page.data?.settings?.show_get_started !== false}
							<button
								onclick={() => {
									openState = false;
									dispatch('getStarted');
								}}
								class="cursor-pointer flex items-center gap-2 w-full px-4 py-2.5 text-left text-sm hover:bg-surface-200-800 disabled:text-surface-400-600 text-surface-950-50"
								data-testid="get-started-button"
								><i class="fa-solid fa-rocket mr-2"></i>{m.getStarted()}</button
							>
						{/if}
						{#if !page.data?.user?.is_third_party}
							<button
								onclick={() => {
									openState = false;
									modalBuildInfo();
								}}
								class="cursor-pointer flex items-center gap-2 w-full px-4 py-2.5 text-left text-sm hover:bg-surface-200-800 disabled:text-surface-400-600 text-surface-950-50"
								data-testid="about-button"
								><i class="fa-solid fa-circle-info mr-2"></i>{m.aboutCiso()}</button
							>
						{/if}
						<a
							href="https://intuitem.gitbook.io/ciso-assistant"
							target="_blank"
							class="unstyled cursor-pointer flex items-center gap-2 w-full px-4 py-2.5 text-left text-sm hover:bg-surface-200-800 disabled:text-surface-400-600 text-surface-950-50"
							data-testid="docs-button"><i class="fa-solid fa-book mr-2"></i>{m.onlineDocs()}</a
						>
						<form action="/logout" method="POST" onsubmit={() => breadcrumbs.clear()}>
							<button class="w-full" type="submit" data-testid="logout-button">
								<span
									class="flex items-center gap-2 w-full px-4 py-2.5 text-left text-sm hover:bg-surface-200-800 disabled:text-surface-400-600 text-surface-950-50"
									><i class="fa-solid fa-right-from-bracket mr-2"></i>{m.Logout()}</span
								>
							</button>
						</form>
					</div>
				{/if}
			</div>
		{:else}
			<button
				class="btn bg-initial"
				data-testid="sidebar-more-btn-disabled"
				aria-label="More options"
				id="sidebar-more-btn-disabled"><i class="fa-solid fa-ellipsis-vertical"></i></button
			>
		{/if}
	</div>
</div>
