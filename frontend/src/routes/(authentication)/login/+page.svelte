<script lang="ts">
	import type { ActionData, PageData } from './$types';
	import Logo from '$lib/components/Logo/Logo.svelte';
	import FormCard from './FormCard.svelte';
	import { m } from '$paraglide/messages';

	interface Props {
		data: PageData;
		form: ActionData;
	}

	let { data, form }: Props = $props();

	const pillars = [
		{ icon: 'fa-layer-group', label: m.frameworks() },
		{ icon: 'fa-shield-halved', label: m.riskAssessments() },
		{ icon: 'fa-clipboard-check', label: m.audits() }
	];
</script>

<svelte:head>
	<title>10A GRC Lab | {m.login()}</title>
</svelte:head>

<main class="auth-shell">
	<section class="auth-note" aria-labelledby="workspace-heading">
		<!-- .dark scopes the logo's dark: variant so the wordmark reads on this panel in both themes -->
		<div class="dark flex items-center gap-4">
			<Logo />
		</div>
		<div>
			<p class="mb-5 text-[11px] font-extrabold uppercase tracking-[0.18em] text-white/60">
				Governance · Risk · Compliance
			</p>
			<h1 id="workspace-heading">
				{m.yourStreamlined()}
				<span class="auth-note__accent">{m.oneStopShop()}</span>
				{m.forComplianceRiskManagement()}
			</h1>
		</div>
		<div>
			<ul class="auth-note__pillars">
				{#each pillars as { icon, label }}
					<li>
						<i class="fa-solid {icon}" aria-hidden="true"></i>
						{label}
					</li>
				{/each}
			</ul>
			<p class="mt-6 text-xs tracking-[0.08em] text-white/50">10Alytics · 10A GRC Lab</p>
		</div>
	</section>

	<section class="auth-panel" aria-labelledby="sign-in-heading">
		<div class="w-[min(100%,24rem)]">
			<!-- the brand panel is hidden below lg, so the form carries the logo there -->
			<div class="mb-10 lg:hidden"><Logo /></div>
			<h2 id="sign-in-heading" class="text-surface-950-50">{m.logIntoYourAccount()}</h2>
			<p class="mt-3 leading-relaxed text-surface-600-400">{m.youNeedToLogIn()}</p>
			<div class="mt-8">
				<FormCard {data} {form} />
			</div>
			<p class="mt-10 text-center text-xs text-surface-500">
				Powered by CISO Assistant ·
				<a
					class="underline-offset-2 hover:text-surface-950-50 hover:underline"
					href="https://github.com/10Alytics-Engineering/grc-ciso-assistant-community"
					target="_blank"
					rel="noopener noreferrer">Source code (AGPL-3.0)</a
				>
			</p>
		</div>
	</section>
</main>
