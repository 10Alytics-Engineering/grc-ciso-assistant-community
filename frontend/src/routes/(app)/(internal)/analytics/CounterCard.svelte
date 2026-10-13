<script lang="ts">
	import { goto } from '$lib/utils/breadcrumbs';

	interface Props {
		count?: number;
		label: string;
		faIcon?: string;
		iconColor?: string;
		href?: string | undefined;
		children?: import('svelte').Snippet;
	}

	let {
		count = 0,
		label,
		faIcon = '',
		iconColor = '',
		href = undefined,
		children
	}: Props = $props();

	const clickHandler = () => {
		if (href) {
			goto(href, { breadcrumbAction: 'push', label });
		}
	};
</script>

<!-- One cell of a .stat-strip (admin panel KPI style). -->
<div
	class="group flex flex-col whitespace-normal transition-colors {href
		? 'cursor-pointer hover:bg-surface-100-900'
		: ''}"
	onclick={clickHandler}
	onkeydown={(e) => href && (e.key === 'Enter' || e.key === ' ') && clickHandler()}
	role={href ? 'link' : undefined}
	tabindex={href ? 0 : undefined}
>
	<p class="label-caps">{label}</p>
	<div class="mt-3 flex flex-row items-center justify-between gap-3">
		<div
			class="text-3xl font-medium tabular-nums text-surface-950-50 sm:text-4xl"
			style="font-family: var(--typo-heading--font-family)"
			data-testid="card-{label}"
		>
			{count?.toLocaleString()}
		</div>
		{#if faIcon}
			<span
				class="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary-50-950 {iconColor ||
					'text-primary-500'}"
				aria-hidden="true"
			>
				<i class="{faIcon} text-sm"></i>
			</span>
		{/if}
		{@render children?.()}
	</div>
	{#if href}
		<div class="mt-1 flex justify-end">
			<i
				class="fa-solid fa-arrow-right text-xs text-surface-400-600 transition-transform group-hover:translate-x-1 group-hover:text-primary-600-400"
				aria-hidden="true"
			></i>
		</div>
	{/if}
</div>
