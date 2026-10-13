<script lang="ts">
	interface Props {
		title: string;
		icon?: string;
		description?: string;
		maxColumns?: 2 | 3 | 4;
		children: import('svelte').Snippet;
	}

	let { title, icon = '', description = '', maxColumns = 4, children }: Props = $props();

	// Generate responsive grid classes based on maxColumns
	const gridClasses = $derived(() => {
		switch (maxColumns) {
			case 2:
				return 'grid grid-cols-2 gap-3';
			case 3:
				return 'grid grid-cols-2 @lg:grid-cols-3 gap-3';
			case 4:
			default:
				return 'grid grid-cols-2 @lg:grid-cols-3 @2xl:grid-cols-4 gap-3';
		}
	});
</script>

<!-- Columns follow the group's own width (container query), not the viewport. -->
<section class="@container space-y-3">
	<div class="flex items-center gap-3">
		{#if icon}
			<span
				class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-primary-50-950 text-primary-600-400"
				aria-hidden="true"
			>
				<i class="{icon} text-sm"></i>
			</span>
		{/if}
		<div>
			<h3 class="text-lg font-medium text-surface-950-50">{title}</h3>
			{#if description}
				<p class="text-sm text-surface-600-400">{description}</p>
			{/if}
		</div>
	</div>

	<div class={gridClasses()}>
		{@render children()}
	</div>
</section>
