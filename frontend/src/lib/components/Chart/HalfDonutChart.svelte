<script lang="ts">
	import { onMount } from 'svelte';

	import { mountThemeAwareChart } from '$lib/utils/echartsTheme';
	import { safeTranslate } from '$lib/utils/i18n';

	import { level } from '$paraglide/messages';
	interface riskChartData {
		name: string;
		value: number;
		color: string;
	}

	interface Props {
		width?: string;
		height?: string;
		classesContainer?: string;
		title?: string;
		name: string;
		values: riskChartData[]; // Set the types for these variables later on
		colors?: string[];
	}

	let {
		width = 'w-auto',
		height = 'h-full',
		classesContainer = '',
		title = '',
		name,
		values = $bindable(),
		colors = []
	}: Props = $props();

	for (const index in values) {
		if (values[index].name) {
			values[index].name = safeTranslate(values[index].name);
		}
	}
	const chart_id = `${name}_div`;
	onMount(() => {
		let dispose: (() => void) | undefined;
		let active = true;
		(async () => {
			const echarts = await import('echarts');
			if (!active) return;
			const el = document.getElementById(chart_id);
			if (!el) return;
			const total = values.reduce((sum, v) => sum + (Number(v.value) || 0), 0);
			dispose = mountThemeAwareChart(echarts, el, () => ({
				title: [
					{ text: title, left: 0, top: 0 },
					// Total in the arc's centre: the one number this chart is about.
					{
						text: String(total),
						left: 'center',
						top: '52%',
						textStyle: { fontSize: 28, fontWeight: 500 }
					}
				],
				tooltip: { trigger: 'item', formatter: '{b}: <b>{c}</b> ({d}%)' },
				legend: { bottom: 0, left: 'center' },
				series: [
					{
						name: level(),
						type: 'pie',
						radius: ['62%', '92%'],
						center: ['50%', '72%'],
						startAngle: 180,
						endAngle: 360,
						// Labels around a half donut collide and clip; legend + tooltip carry identity.
						label: { show: false },
						labelLine: { show: false },
						data: values,
						color: colors
					}
				]
			}));
		})();
		return () => {
			active = false;
			dispose?.();
		};
	});
</script>

<div id={chart_id} class="{width} {height} {classesContainer}"></div>
