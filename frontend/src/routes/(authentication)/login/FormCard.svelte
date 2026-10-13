<script lang="ts">
	import { run } from 'svelte/legacy';
	import { onMount } from 'svelte';

	import SuperForm from '$lib/components/Forms/Form.svelte';
	import TextField from '$lib/components/Forms/TextField.svelte';
	import { loginSchema } from '$lib/utils/schemas';

	import { page } from '$app/state';
	import { redirectToProvider } from '$lib/allauth.js';
	import { getSecureRedirect } from '$lib/utils/helpers';
	import { zod4 as zod } from 'sveltekit-superforms/adapters';
	import MfaAuthenticateModal from './mfa/components/MFAAuthenticateModal.svelte';
	import { m } from '$paraglide/messages';
	import {
		getModalStore,
		type ModalComponent,
		type ModalSettings,
		type ModalStore
	} from '$lib/components/Modals/stores';

	interface Props {
		data: any;
		form: any;
	}

	let { data, form }: Props = $props();

	let showPassword = $state(false);

	const modalStore: ModalStore = getModalStore();

	function modalMFAAuthenticate(): void {
		const mfaTypes: string[] = form?.mfaFlow?.types ?? ['totp'];
		const modalComponent: ModalComponent = {
			ref: MfaAuthenticateModal,
			props: {
				_form: data.mfaAuthenticateForm,
				formAction: '?/mfaAuthenticate',
				mfaTypes
			}
		};
		const modal: ModalSettings = {
			type: 'component',
			component: modalComponent,
			// Data
			title: m.mfaAuthenticateTitle(),
			body: m.enterCodeGeneratedByApp()
		};
		modalStore.trigger(modal);
	}

	run(() => {
		form && form.mfaFlow ? modalMFAAuthenticate() : null;
	});

	function getSSOCallbackURL(callbackURL: string): string {
		const url = new URL(callbackURL);
		const next = getSecureRedirect(page.url.searchParams.get('next')) || '/';

		url.pathname = '/sso/authenticate';
		url.search = '';
		url.searchParams.set('next', next);
		return url.toString();
	}

	function triggerSSO(): void {
		redirectToProvider(
			data.SSOInfo.sp_entity_id,
			getSSOCallbackURL(data.SSOInfo.callback_url),
			'login'
		);
	}

	// `/login?sso` (optionally with `&next=`) skips the form and goes straight to
	// the identity provider. Excluded users (keep_local_login) can still reach the
	// form via plain `/login`.
	const autoSSO = $derived(data.SSOInfo?.is_enabled && page.url.searchParams.has('sso'));

	onMount(() => {
		if (autoSSO) triggerSSO();
	});
</script>

<div data-testid="login" class="flex w-full flex-col space-y-4">
	{#if autoSSO}
		<p class="flex items-center gap-3 text-sm text-surface-600-400">
			<i class="fa-solid fa-circle-notch fa-spin text-primary-500" aria-hidden="true"></i>
			{m.loginSSO()}…
		</p>
	{:else}
		<SuperForm
			class="flex flex-col space-y-3"
			data={data?.form}
			dataType="form"
			validators={zod(loginSchema)}
			action="?/login&next={page.url.searchParams.get('next') || '/'}"
		>
			{#snippet children({ form, delayed })}
				<TextField
					type="email"
					{form}
					field="username"
					label={m.email()}
					class="h-11"
					autocomplete="username"
				/>
				<div class="relative">
					<TextField
						type={showPassword ? 'text' : 'password'}
						{form}
						field="password"
						label={m.password()}
						class="h-11 pr-11"
						autocomplete="current-password"
					/>
					<button
						type="button"
						class="absolute right-0 bottom-0 grid h-11 w-11 place-items-center text-surface-500 hover:text-surface-950-50"
						aria-label="{showPassword ? m.hide() : m.show()} {m.password()}"
						aria-pressed={showPassword}
						onclick={() => (showPassword = !showPassword)}
					>
						<i class="fa-regular {showPassword ? 'fa-eye-slash' : 'fa-eye'}" aria-hidden="true"></i>
					</button>
				</div>
				<div class="flex flex-row justify-end">
					<a
						href="/password-reset"
						class="text-sm text-primary-600-400 hover:underline"
						data-testid="forgot-password-btn"
					>
						{m.forgtPassword()}?
					</a>
				</div>
				<button
					class="btn preset-filled-primary-500 group h-11 w-full font-semibold"
					data-testid="login-btn"
					type="submit"
					disabled={delayed}
				>
					{#if delayed}
						<i class="fa-solid fa-circle-notch fa-spin" aria-hidden="true"></i>
						{m.loading()}…
					{:else}
						{m.login()}
						<i
							class="fa-solid fa-arrow-right text-xs transition-transform group-hover:translate-x-0.5"
							aria-hidden="true"
						></i>
					{/if}
				</button>
			{/snippet}
		</SuperForm>
		{#if data.SSOInfo.is_enabled}
			<div class="flex items-center gap-3 text-sm text-surface-600-400">
				<hr class="flex-1 border-surface-200-800" />
				{m.or()}
				<hr class="flex-1 border-surface-200-800" />
			</div>
			<button
				class="btn h-11 w-full border border-surface-200-800 bg-surface-50-950 font-semibold hover:bg-surface-100-900"
				onclick={triggerSSO}>{m.loginSSO()}</button
			>
		{/if}
	{/if}
</div>
