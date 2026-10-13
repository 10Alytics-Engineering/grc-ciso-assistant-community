<script lang="ts">
	import Anchor from '$lib/components/Anchor/Anchor.svelte';

	interface Props {
		count?: string;
		label: string;
		href?: string;
		emphasis?: boolean;
		customClass?: string;
		raw?: boolean;
	}

	let {
		count = '0',
		label,
		href = '#',
		emphasis = false,
		customClass = '',
		raw = false
	}: Props = $props();

	// Admin-panel KPI cell: bordered, flat, label above a display number. Emphasis is a small
	// brand marker on the label rather than a coloured side bar.
	const baseCardClasses = `
		flex flex-col justify-between p-4 rounded-xl border border-surface-200-800
		bg-surface-50-950 transition-colors group cursor-pointer hover:bg-surface-100-900
		${customClass}
	`;

	// Format count with proper formatting for numbers, percentages, and ratios
	const formattedCount = $derived(() => {
		// Convert to string first to handle both string and number inputs
		const countStr = String(count);

		// Skip formatting when value is already pre-formatted (e.g. currency strings)
		if (raw) return countStr;

		// If it already contains % or /, return as-is since it's already formatted
		if (countStr.includes('%') || countStr.includes('/')) {
			return countStr;
		}

		// Try to parse as number for thousand separators
		const numericCount = parseInt(countStr);
		return isNaN(numericCount) ? countStr : numericCount.toLocaleString();
	});
</script>

{#snippet cardContent()}
	<p class="label-caps flex items-start gap-1.5">
		{#if emphasis}
			<span class="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary-500" aria-hidden="true"></span>
		{/if}
		<span class="line-clamp-2">{label}</span>
	</p>
	<div class="mt-2 flex items-end justify-between gap-2">
		<span
			class="text-3xl font-medium leading-none tabular-nums text-surface-950-50"
			style="font-family: var(--typo-heading--font-family)">{formattedCount()}</span
		>
		<i
			class="fa-solid fa-arrow-right text-[11px] text-surface-400-600 transition-transform group-hover:translate-x-0.5 group-hover:text-primary-600-400"
			aria-hidden="true"
		></i>
	</div>
{/snippet}

{#if href && href !== '#'}
	<Anchor {href} {label} class="{baseCardClasses} text-surface-950-50">
		{@render cardContent()}
	</Anchor>
{:else}
	<div class="{baseCardClasses} text-surface-950-50">
		{@render cardContent()}
	</div>
{/if}
