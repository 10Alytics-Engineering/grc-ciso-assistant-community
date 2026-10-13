<script lang="ts">
	import { page } from '$app/state';
	import { safeTranslate } from '$lib/utils/i18n';
	import Anchor from '$lib/components/Anchor/Anchor.svelte';

	interface Props {
		// `key` distinguishes entries that share a label (and so a visibility flag).
		item?: { name: string; href: string; fa_icon: string; key?: string }[];
		sideBarVisibleItems: Record<string, boolean>;
	}

	let { item = [], sideBarVisibleItems }: Props = $props();

	// Entries that preselect a filter carry a query string, so match on it too —
	// otherwise `/campaigns?kind=internal` would never highlight.
	let classesActive = $derived((href: string) =>
		href === page.url.pathname || href === `${page.url.pathname}${page.url.search}`
			? 'sidebar-link sidebar-link--active'
			: 'sidebar-link'
	);
</script>

{#each item as item}
	<!-- undefined and true must be shown -->
	{#if sideBarVisibleItems[item.name] !== false}
		<Anchor
			href={item.href}
			breadcrumbAction="replace"
			class="unstyled whitespace-nowrap {classesActive(item.href ?? '')}"
			aria-current={classesActive(item.href ?? '').includes('active') ? 'page' : undefined}
			data-testid={'accordion-item-' + item.href.substring(1)}
		>
			<span
				class="flex items-center w-full gap-3 min-w-0"
				id={item.key ?? item.name}
				title={safeTranslate(item.name)}
			>
				<i class="{item.fa_icon} w-4 shrink-0 text-center text-xs" aria-hidden="true"></i>
				<span class="truncate">{safeTranslate(item.name)}</span>
			</span>
		</Anchor>
	{/if}
{/each}
