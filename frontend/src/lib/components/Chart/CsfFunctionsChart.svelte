<script lang="ts">
	import { onMount } from 'svelte';
	import { mountThemeAwareChart } from '$lib/utils/echartsTheme';
	import { safeTranslate } from '$lib/utils/i18n';
	import { m } from '$paraglide/messages';

	interface Props {
		name?: string;
		values: { name: string; value: number }[];
	}

	let { name = 'csf-functions', values }: Props = $props();

	// CSF functions are ordinal: keep the framework's order instead of sorting by count.
	const ORDER = ['Govern', 'Identify', 'Protect', 'Detect', 'Respond', 'Recover', '(undefined)'];

	const chart_id = `${name}_div`;
	onMount(() => {
		let dispose: (() => void) | undefined;
		let active = true;
		(async () => {
			const echarts = await import('echarts');
			if (!active) return;
			const el = document.getElementById(chart_id);
			if (!el) return;
			dispose = mountThemeAwareChart(echarts, el, () => {
				// Backend ships display labels ("Govern", "(undefined)"); normalize back to raw keys.
				const label = (n: string) => safeTranslate(n.replace(/[()]/g, ''));
				const rank = (n: string) => (ORDER.includes(n) ? ORDER.indexOf(n) : ORDER.length);
				const rows = [...values].sort((a, b) => rank(a.name) - rank(b.name));
				return {
					title: { text: m.csfFunction(), left: 0, top: 0 },
					tooltip: { trigger: 'item', formatter: (p: any) => `${label(p.name)}: <b>${p.value}</b>` },
					grid: { left: 8, right: 36, top: 36, bottom: 0, containLabel: true },
					xAxis: { type: 'value', minInterval: 1, splitNumber: 3 },
					yAxis: {
						type: 'category',
						inverse: true,
						data: rows.map((r) => r.name),
						axisLabel: { formatter: label },
						axisLine: { show: false }
					},
					series: [
						{
							type: 'bar',
							barWidth: 16,
							// Single series: one hue, no legend; square at the baseline, 4px at the end.
							itemStyle: { borderRadius: [0, 4, 4, 0] },
							label: { show: true, position: 'right', fontSize: 11, textBorderWidth: 0 },
							data: rows.map((r) => r.value)
						}
					]
				};
			});
		})();
		return () => {
			active = false;
			dispose?.();
		};
	});
</script>

<div id={chart_id} class="h-full w-auto"></div>
