<script lang="ts">
	import { navData } from '$lib/components/SideBar/navData';

	import SideBarItem from '$lib/components/SideBar/SideBarItem.svelte';
	import SideBarCategory from '$lib/components/SideBar/SideBarCategory.svelte';
	import { Accordion } from '@skeletonlabs/skeleton-svelte';
	import { page } from '$app/state';
	import { canSeeNavItem } from '$lib/components/SideBar/navVisibility';
	import { driverInstance } from '$lib/utils/stores';

	const user = page.data.user;

	const items = navData.items
		.map((item) => ({
			...item,
			// Shared with the command palette so the two cannot offer different sets of pages.
			items: item.items.filter((subItem) => canSeeNavItem(subItem, user))
		}))
		.filter((item) => item.items.length > 0); // Filter out items with no sub-items

	import { lastAccordionItem } from '$lib/utils/stores';
	interface Props {
		sideBarVisibleItems: Record<string, boolean>;
	}

	let { sideBarVisibleItems }: Props = $props();

	function handleValueChange(details: { value: string[] }) {
		$lastAccordionItem = details.value;
		setTimeout(() => {
			$driverInstance?.moveNext();
		}, 0);
	}
</script>

<nav class="grow min-h-0 overflow-y-auto px-3 py-5 scrollbar" style="overscroll-behavior: contain">
	<Accordion
		value={$lastAccordionItem}
		onValueChange={handleValueChange}
		collapsible
		class="space-y-3"
	>
		{#each items as item}
			{#if sideBarVisibleItems && sideBarVisibleItems[item.name] !== false && item.items.some((subItem) => sideBarVisibleItems[subItem.name] !== false)}
				<Accordion.Item value={item.name} id={item.name.toLowerCase().replace(' ', '-')}>
					<Accordion.ItemTrigger class="sidebar-section-label cursor-pointer">
						<SideBarCategory {item} />
						<Accordion.ItemIndicator
							class="transition-transform duration-200 data-[state=open]:rotate-0 data-[state=closed]:-rotate-90"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								width="10px"
								height="10px"
								viewBox="0 0 448 512"
								fill="currentColor"
							>
								<path
									d="M201.4 374.6c12.5 12.5 32.8 12.5 45.3 0l160-160c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L224 306.7 86.6 169.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l160 160z"
								/>
							</svg>
						</Accordion.ItemIndicator>
					</Accordion.ItemTrigger>
					<Accordion.ItemContent class="mt-1 space-y-0.5">
						<SideBarItem item={item.items} {sideBarVisibleItems} />
					</Accordion.ItemContent>
				</Accordion.Item>
			{/if}
		{/each}
	</Accordion>
</nav>
