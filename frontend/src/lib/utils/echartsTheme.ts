import { browser } from '$app/environment';

/* 10A categorical order, brand orange first. Validated with the dataviz palette checker
   (adjacent CVD ΔE >= 8.4, normal-vision >= 19.3) against #ffffff and #141517.
   Past 3 series in scatter-like forms, fold to "Other" rather than adding hues. */
const SERIES_LIGHT = ['#da6728', '#2a78d6', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'];
const SERIES_DARK = ['#da6728', '#3987e5', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'];

/** Chart defaults matching the 10alytics admin surfaces; series-level options still win. */
function brandTheme(dark: boolean) {
	const ink = dark ? '#f9fafb' : '#1c0d05';
	const muted = dark ? '#9aa0a6' : '#495057';
	const rule = dark ? '#24272d' : '#ebebeb';
	const surface = dark ? '#141517' : '#ffffff';
	const axis = {
		axisLine: { show: true, lineStyle: { color: rule } },
		axisTick: { show: false },
		axisLabel: { color: muted, fontSize: 11 },
		splitLine: { show: true, lineStyle: { color: rule, type: 'solid', width: 1 } },
		nameTextStyle: { color: muted, fontSize: 11 }
	};
	return {
		color: dark ? SERIES_DARK : SERIES_LIGHT,
		backgroundColor: 'transparent',
		textStyle: { fontFamily: "'BR Firma', ui-sans-serif, system-ui, sans-serif", color: ink },
		title: {
			textStyle: {
				color: ink,
				fontFamily: "'Cabinet Grotesk', 'BR Firma', sans-serif",
				fontWeight: 600,
				fontSize: 14
			},
			subtextStyle: { color: muted, fontSize: 12 }
		},
		legend: {
			icon: 'roundRect',
			itemWidth: 10,
			itemHeight: 10,
			itemGap: 14,
			textStyle: { color: muted, fontSize: 12 }
		},
		tooltip: {
			backgroundColor: surface,
			borderColor: rule,
			borderWidth: 1,
			padding: [8, 12],
			textStyle: { color: ink, fontSize: 12 },
			extraCssText: 'border-radius: 8px; box-shadow: 0 8px 24px rgb(0 0 0 / 0.08);'
		},
		categoryAxis: { ...axis, splitLine: { show: false } },
		valueAxis: { ...axis, axisLine: { show: false } },
		logAxis: { ...axis, axisLine: { show: false } },
		timeAxis: { ...axis, splitLine: { show: false } },
		// 1px surface-coloured edge on each mark = the 2px gap between touching segments.
		bar: {
			barMaxWidth: 24,
			itemStyle: { borderColor: surface, borderWidth: 1 },
			// Text wears ink, not an outline inherited from the mark edge.
			label: { color: muted, textBorderWidth: 0 }
		},
		line: { lineStyle: { width: 2 }, symbol: 'circle', symbolSize: 8, smooth: false },
		pie: {
			itemStyle: { borderColor: surface, borderWidth: 2, borderRadius: 4 },
			label: { color: muted },
			labelLine: { lineStyle: { color: rule } }
		},
		radar: {
			axisName: { color: muted },
			splitLine: { lineStyle: { color: rule } },
			splitArea: { show: false },
			axisLine: { lineStyle: { color: rule } }
		},
		heatmap: { itemStyle: { borderColor: surface, borderWidth: 2 } },
		sankey: { lineStyle: { color: 'gradient', opacity: 0.25 }, label: { color: ink } }
	};
}

let themesRegistered = false;
function registerBrandThemes(echarts: any) {
	if (themesRegistered) return;
	echarts.registerTheme('10a-light', brandTheme(false));
	echarts.registerTheme('10a-dark', brandTheme(true));
	themesRegistered = true;
}

export function isDarkTheme(): boolean {
	return browser && document.documentElement.classList.contains('dark');
}

interface ThemeAwareChartOptions {
	rendererOpts?: Record<string, any>;
	/** Called after every (re)init so the component can attach instance-level
	 *  listeners (e.g. chart.on('click', …)) that don't survive a dispose. */
	onChart?: (chart: any) => void;
	/** Set false when the caller installs its own resize handling (e.g. a debounced
	 *  one for an expensive layout) and does not want the built-in listener too. */
	manageResize?: boolean;
}

/**
 * Inits an ECharts instance that rebuilds itself whenever the `dark` class on
 * <html> flips. `buildOption` is re-invoked on each theme change, so inline
 * theme-conditional colors are recomputed instead of frozen at first paint.
 * Returns a dispose function.
 */
export function mountThemeAwareChart(
	echarts: any,
	container: HTMLElement,
	buildOption: () => any,
	{ rendererOpts = { renderer: 'svg' }, onChart, manageResize = true }: ThemeAwareChartOptions = {}
): () => void {
	registerBrandThemes(echarts);
	let dark = isDarkTheme();
	let chart: any;
	let firstPaint = true;

	const init = () => {
		chart = echarts.init(container, dark ? '10a-dark' : '10a-light', rendererOpts);
		const option = { ...buildOption(), backgroundColor: 'transparent' };
		// A theme-flip re-init must snap straight to the final frame: animating it looks
		// janky live, and window.print() can capture the chart mid-animation (blank/partial
		// in PDF exports). Only the very first mount keeps its entry animation.
		if (!firstPaint) option.animation = false;
		chart.setOption(option, true);
		onChart?.(chart);
		firstPaint = false;
	};
	init();
	container.setAttribute('data-theme-managed', 'true');

	const resize = () => chart?.resize();
	if (manageResize) window.addEventListener('resize', resize);

	// Containers resize without the window doing so (detail tables, accordions, tabs).
	// rAF-batched so a resize cannot loop.
	let pending = 0;
	const sizeObserver =
		!manageResize || typeof ResizeObserver === 'undefined'
			? undefined
			: new ResizeObserver(() => {
					cancelAnimationFrame(pending);
					pending = requestAnimationFrame(resize);
				});
	sizeObserver?.observe(container);

	const observer = new MutationObserver(() => {
		const now = isDarkTheme();
		if (now === dark) return;
		dark = now;
		chart.dispose();
		init();
	});
	observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

	return () => {
		observer.disconnect();
		sizeObserver?.disconnect();
		cancelAnimationFrame(pending);
		if (manageResize) window.removeEventListener('resize', resize);
		container.removeAttribute('data-theme-managed');
		chart.dispose();
	};
}
