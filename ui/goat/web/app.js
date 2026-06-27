// ─────────────────────────────────────────────────────────────────
// Le Goat — Logique UI (vanilla JS, aucune dépendance externe)
//
// Architecture JS :
//   S            → état global persisté en localStorage
//   t(key)       → fonction de traduction (accède à T[S.lang][key])
//   applyXxx()   → applique un paramètre UI et le sauvegarde
//   renderXxx()  → re-génère un composant DOM
//   openXxx()    → ouvre une modale / dropdown
//   updateXxx()  → met à jour l'affichage sans recréer le DOM
//
// Pour ajouter un mode côté JS :
//   Les modes sont injectés via %%MODES_JSON%% — aucune modification JS
//   n'est nécessaire. Voir AppConfig.MODE_OPTIONS (Python).
//
// Pour ajouter un paramètre persisté :
//   1. Ajoutez une clé dans l'objet S avec sa valeur par défaut.
//   2. Créez une fonction applyMonParam(v, snd) qui appelle apply().
//   3. Liez l'événement UI et ajoutez l'init dans la section "Init".
// ─────────────────────────────────────────────────────────────────
!function(){"use strict";
const $=i=>document.getElementById(i),$$=s=>Array.from(document.querySelectorAll(s));
const T=%%TRANSLATIONS_JSON%%,WP=%%WELCOME_JSON%%,ST=%%STATUS_JSON%%,MO=%%MODES_JSON%%,DM=%%DISABLED_MODES_JSON%%,titleByLang=%%TITLE_BY_LANG_JSON%%,models=%%MODELS_JSON%%,wStyles=%%WSTYLES_JSON%%,gadgets=%%GADGETS_JSON%%,SP=%%STORAGE_PREFIX_JSON%%,appVersion=%%VERSION_JSON%%,sheetLimits=%%SHEET_LIMITS_JSON%%,migrationPrompt=%%MIGRATION_PROMPT_JSON%%,localProfilePresets=%%PROFILE_PRESETS_JSON%%;
const defs={lang:%%DEFAULT_LANG_JSON%%,theme:%%DEFAULT_THEME_JSON%%,effects:%%DEFAULT_EFFECTS_JSON%%,textSize:%%DEFAULT_TEXTSIZE_JSON%%,uiScale:100,accent:'blue',wallpaperNormalType:'none',wallpaperNormalSrc:'',wallpaperNormalVolume:35,wallpaperCoworkingType:'none',wallpaperCoworkingSrc:'',wallpaperCoworkingVolume:35,optResp:%%DEFAULT_OPTRESP_JSON%%,uiOpt:%%DEFAULT_UIOPT_JSON%%,kbSound:%%DEFAULT_KB_SOUND_JSON%%,kbStyle:%%DEFAULT_KB_STYLE_JSON%%,clickSound:%%DEFAULT_CLICK_SOUND_JSON%%,clickStyle:%%DEFAULT_CLICK_STYLE_JSON%%,aiSound:%%DEFAULT_AI_SOUND_JSON%%,mode:%%DEFAULT_MODE_JSON%%,model:%%DEFAULT_MODEL_JSON%%,wstyle:%%DEFAULT_WSTYLE_JSON%%,gadget:%%DEFAULT_GADGET_JSON%%,calcTarget:%%DEFAULT_CALC_TARGET_JSON%%,aifont:'default',userfont:'default',overclock:'off',videoFps:'30',videoQuality:'1080p',otherModelsOn:%%DEFAULT_OTHER_MODELS_JSON%%,uiStyle:%%DEFAULT_UI_STYLE_JSON%%,glassTransparency:%%DEFAULT_GLASS_TRANSPARENCY_JSON%%,glassTint:%%DEFAULT_GLASS_TINT_JSON%%,pixelButtons:%%DEFAULT_PIXEL_BUTTONS_JSON%%,aiTyping:%%DEFAULT_AI_TYPING_EFFECT_JSON%%,aiTypingStyle:'default',sendEffects:'on',reflexBoost:'off'};
const CUSTOM_MODEL_SENTINEL=%%CUSTOM_MODEL_SENTINEL_JSON%%;
const ls=(k,v)=>{try{if(v!==undefined){localStorage.setItem(SP+'-'+k,v);return v}return localStorage.getItem(SP+'-'+k)}catch(err){console.warn('Local storage unavailable for',k,err);return v!==undefined?v:null}};
const shell=$('shell'),msgBox=$('messages'),form=$('chat-form'),ta=$('message-input'),sendBtn=$('send-button'),statusEl=$('status'),welcomeEl=$('welcome-copy'),welcomeDesc=$('welcome-desc'),brandText=$('brand-text');
const controlsRow=$('controls-row'),modePanel=$('mode-panel');
const modeTrigger=$('mode-trigger'),modeMenu=$('mode-menu'),modeLbl=$('selected-mode-label'),modeIcn=$('mode-icon'),modeAnn=$('mode-announcement');
const styleTrigger=$('style-trigger'),styleMenu=$('style-menu'),styleLbl=$('selected-style-label'),styleIcn=$('style-icon');
/* Gadgets desactive pour le moment
const gadgetTrigger=$('gadget-trigger'),gadgetMenu=$('gadget-menu'),gadgetLbl=$('selected-gadget-label'),gadgetIcn=$('gadget-icon');
*/
const modelTriggerBtn=$('model-trigger-btn'),modelDDMenu=$('model-dd-menu'),modelCurrentLabel=$('model-current-label');
// ── Modèles personnalisés (Settings → Personnalisation → Autres modèles) ──
const otherModelsToggle=$('other-models-toggle');
const customModelsPanel=$('custom-models-panel'),customModelsTrigger=$('custom-models-trigger'),customModelsMenu=$('custom-models-menu'),customModelsLabel=$('custom-models-label');
const customModelBackdrop=$('custom-model-backdrop'),customModelInput=$('custom-model-name-input'),customModelEnterBtn=$('custom-model-enter-btn'),customModelCancelBtn=$('custom-model-cancel-btn'),customModelTitleEl=$('custom-model-modal-title'),customModelErrorEl=$('custom-model-error');
const tabChat=$('tab-chat'),tabCoworking=$('tab-coworking');
const privateChatBtn=$('private-chat-btn');
const composerPlus=$('composer-plus'),plusMenu=$('plus-menu'),plusAddSheet=$('plus-add-sheet'),sheetsRow=$('sheets-row');
const sheetBackdrop=$('sheet-modal-backdrop'),sheetTA=$('sheet-textarea'),sheetAddBtn=$('sheet-add-btn'),sheetCancelBtn=$('sheet-cancel'),sheetTitle=$('sheet-modal-title');
const sheetCharCounter=$('sheet-char-counter');
const migrateBackdrop=$('migrate-backdrop'),migrateTA=$('migrate-textarea'),migrateAddBtn=$('migrate-add-btn'),migrateCancelBtn=$('migrate-cancel-btn'),migrateTitle=$('migrate-title'),migratePromptBox=$('migrate-prompt-box'),migrateStep1=$('migrate-step1'),migrateStep2=$('migrate-step2'),migrateCloseX=$('migrate-close-x');
const modal=$('settings-modal'),backdrop=$('settings-backdrop'),dragH=$('settings-drag-handle'),tooltipEl=$('tooltip');
const charCounterEl=$('char-counter'),charCounterText=$('char-counter-text'),charCounterTip=$('char-counter-tip');
const stopBtn=$('stop-button');
const voiceInputBtn=$('voice-input-btn');
const contractionTag=$('contraction-tag'),contractionTip=$('contraction-tip');
const overclockToggle=$('overclock-toggle'),ocBackdrop=$('overclock-backdrop'),ocWarningText=$('oc-warning-text'),ocConfirmBtn=$('oc-confirm-btn'),ocCancelBtn=$('oc-cancel-btn');
const uiScaleValue=$('ui-scale-value'),scaleDownButton=$('scale-down-button'),scaleUpButton=$('scale-up-button');
const wallpaperLayer=$('wallpaper-layer'),wallpaperImage=$('wallpaper-image'),wallpaperVideo=$('wallpaper-video'),normalWallpaperPreview=$('normal-wallpaper-preview'),coworkingWallpaperPreview=$('coworking-wallpaper-preview');
const wallpaperBackdrop=$('wallpaper-backdrop'),wallpaperModalTitle=$('wallpaper-modal-title'),wallpaperModalTarget=$('wallpaper-modal-target'),wallpaperModalPreview=$('wallpaper-modal-preview'),wallpaperImportImageBtn=$('wallpaper-import-image-btn'),wallpaperImportVideoBtn=$('wallpaper-import-video-btn'),wallpaperRemoveBtn=$('wallpaper-remove-btn'),wallpaperFileInput=$('wallpaper-file-input'),wallpaperVideoFileInput=$('wallpaper-video-file-input'),wallpaperVolumeInput=$('wallpaper-volume-input'),wallpaperVolumeValue=$('wallpaper-volume-value'),wallpaperCloseBtn=$('wallpaper-close-btn');
const calcTargetTrigger=$('calc-target-trigger'),calcTargetMenu=$('calc-target-menu'),calcTargetLabel=$('calc-target-label'),calcTargetIcon=$('calc-target-icon'),calcTargetNotification=$('calc-target-notification');
const profileEditToggle=$('profile-edit-toggle'),profileEditor=$('profile-editor'),profileNamePreview=$('profile-name-preview'),profileDescriptionPreview=$('profile-description-preview'),profileChatCount=$('profile-chat-count'),profileGoatScore=$('profile-goat-score'),profileSocialsPreview=$('profile-socials-preview'),profileAvatarPreview=$('profile-avatar-preview'),profileBannerPreview=$('profile-banner-preview');
const profileAvatarUploadPreview=$('profile-avatar-upload-preview'),profileBannerUploadPreview=$('profile-banner-upload-preview');
const profileFirstnameInput=$('profile-firstname-input'),profileLastnameInput=$('profile-lastname-input'),profileBioInput=$('profile-bio-input'),profileInstagramInput=$('profile-instagram-input'),profileTikTokInput=$('profile-tiktok-input'),profileYouTubeInput=$('profile-youtube-input'),profileGitHubInput=$('profile-github-input'),profileBlueskyInput=$('profile-bluesky-input');
const profileAvatarUploadBtn=$('profile-avatar-upload-btn'),profileBannerUploadBtn=$('profile-banner-upload-btn'),profileAvatarRemoveBtn=$('profile-avatar-remove-btn'),profileBannerRemoveBtn=$('profile-banner-remove-btn'),profileAvatarFile=$('profile-avatar-file'),profileBannerFile=$('profile-banner-file');
const profileShareProBtn=$('profile-share-pro-btn'),profileShareFullBtn=$('profile-share-full-btn');
const profileAvatarMessagesToggle=$('profile-avatar-messages-toggle'),settingsProfileTabAvatar=$('settings-profile-tab-avatar'),settingsProfileTabName=$('settings-profile-tab-name');
const cropBackdrop=$('profile-crop-backdrop'),cropCanvas=$('profile-crop-canvas'),cropZoom=$('profile-crop-zoom'),cropTitle=$('profile-crop-title'),cropApplyBtn=$('profile-crop-apply'),cropCancelBtn=$('profile-crop-cancel'),cropCloseBtn=$('profile-crop-close');
const profileAvatarHoverCard=$('profile-avatar-hover-card'),profileAvatarHoverBanner=$('profile-avatar-hover-banner'),profileAvatarHoverImage=$('profile-avatar-hover-image'),profileAvatarHoverName=$('profile-avatar-hover-name'),profileAvatarHoverBio=$('profile-avatar-hover-bio');
const profilePickerBackdrop=$('profile-picker-backdrop'),profilePickerTitle=$('profile-picker-title'),profilePickerSectionTitle=$('profile-picker-section-title'),profilePickerGrid=$('profile-picker-grid'),profilePickerCloseBtn=$('profile-picker-close');
// ── État global — tout l'état UI persisté en localStorage ────────
// Chaque clé correspond à un réglage sauvegardé entre les sessions.
let S={lang:ls('lang')||defs.lang,theme:ls('theme')||defs.theme,effects:ls('effects')||defs.effects,textSize:ls('textsize')||defs.textSize,uiScale:parseInt(ls('ui-scale')||String(defs.uiScale),10)||defs.uiScale,accent:ls('accent')||defs.accent,wallpaperNormalType:ls('wallpaper-normal-type')||defs.wallpaperNormalType,wallpaperNormalSrc:ls('wallpaper-normal-src')||defs.wallpaperNormalSrc,wallpaperNormalVolume:parseInt(ls('wallpaper-normal-volume')||String(defs.wallpaperNormalVolume),10)||defs.wallpaperNormalVolume,wallpaperCoworkingType:ls('wallpaper-coworking-type')||defs.wallpaperCoworkingType,wallpaperCoworkingSrc:ls('wallpaper-coworking-src')||defs.wallpaperCoworkingSrc,wallpaperCoworkingVolume:parseInt(ls('wallpaper-coworking-volume')||String(defs.wallpaperCoworkingVolume),10)||defs.wallpaperCoworkingVolume,optResp:ls('optresp')||defs.optResp,uiOpt:ls('uiopt')||defs.uiOpt,kbSound:ls('kb-sound')||defs.kbSound,kbStyle:ls('kb-style')||defs.kbStyle,clickSound:ls('click-sound')||defs.clickSound,clickStyle:ls('click-style')||defs.clickStyle,aiSound:ls('ai-sound')||defs.aiSound,mode:ls('mode')||defs.mode,model:ls('model')||defs.model,wstyle:ls('wstyle')||defs.wstyle,gadget:ls('gadget')||defs.gadget,calcTarget:ls('calc-target')||defs.calcTarget,privateChat:false,aifont:ls('aifont')||defs.aifont,userfont:ls('userfont')||defs.userfont,overclock:ls('overclock')||defs.overclock,videoFps:ls('video-fps')||defs.videoFps,videoQuality:ls('video-quality')||defs.videoQuality,aiName:ls('ai-name')||'',aiLogo:ls('ai-logo')||'',otherModelsOn:ls('other-models-on')||defs.otherModelsOn,activeCustomModel:ls('active-custom-model')||'',customModels:(function(){try{const raw=ls('custom-models');return raw?JSON.parse(raw):[]}catch(e){return[]}})(),uiStyle:ls('ui-style')||defs.uiStyle,glassTransparency:(function(){const v=ls('glass-transparency');const n=parseInt(v,10);return Number.isFinite(n)?Math.max(0,Math.min(100,n)):defs.glassTransparency})(),glassTint:ls('glass-tint')||defs.glassTint,pixelButtons:ls('pixel-buttons')||defs.pixelButtons,aiTyping:ls('ai-typing')||defs.aiTyping,aiTypingStyle:ls('ai-typing-style')==='discovery'?'discovery':defs.aiTypingStyle,sendEffects:ls('send-effects')==='off'?'off':defs.sendEffects,reflexBoost:ls('reflex-boost')==='on'?'on':'off'};
// ── Variables runtime (non persistées) ───────────────────────────
let messages=%%MESSAGES_JSON%%,messagesMeta=%%MESSAGES_META_JSON%%,settingsOpen=false,dragging=false,dragSX=0,dragSY=0,mSL=0,mST=0,audioCtx=null,ttTimer=null,avatarHoverTimer=null,profilePickerMode='avatar';
// Stocke quels panneaux « Spécificité » sont ouverts (clé = index du message
// dans la liste `messages`). Permet de conserver l'état d'ouverture entre deux
// appels à renderMessages() (par ex. après un Relancer ou une nouvelle requête).
let openSpecificityPanels=new Set();
let cropState=null;
let wallpaperTarget='normal';
let sheets=[];          // Feuilles d'écriture attachées à la requête courante
let isGenerating=false; // Vrai pendant qu'une réponse IA est en cours
let abortController=null; // Contrôleur pour interrompre la génération
let activeTab='chat';   // Onglet actif : "chat" | "coworking"
// ── Contenu de l'onglet Goat Code (localisé) ─────────────────────
// Pour modifier les messages d'accueil ou le placeholder de Goat Code,
// éditez les valeurs "messages", "placeholder" et "status" ci-dessous.
const coworkingContent={
  fr:{
    placeholder:"Décrivez votre besoin et Goat Code le traduit en code",
    status:"Le code généré par Goat Code est à titre indicatif — il est recommandé de le tester dans un environnement isolé avant toute intégration en production.",
    messages:[
      "Codez intelligemment avec Goat Code — local, rapide, sans compromis.",
      "Décrivez votre logique, Goat Code structure le code pour vous.",
      "De l'idée à l'implémentation, Goat Code pose les fondations techniques."
    ],
    desc:""
  },
  en:{
    placeholder:"Describe your need and Goat Code will write the code",
    status:"Code generated by Goat Code is provided for reference — it is recommended to test it in an isolated environment before any production integration.",
    messages:[
      "Code smarter with Goat Code — local, fast, no compromise.",
      "Describe your logic, Goat Code structures the code for you.",
      "From idea to implementation, Goat Code lays the technical foundation."
    ],
    desc:""
  },
  es:{
    placeholder:"Describa su necesidad y Goat Code lo traducirá en código",
    status:"El código generado por Goat Code es orientativo — se recomienda probarlo en un entorno aislado antes de cualquier integración en producción.",
    messages:[
      "Programe de forma inteligente con Goat Code — local, rápido, sin compromisos.",
      "Describa su lógica y Goat Code estructurará el código por usted.",
      "De la idea a la implementación, Goat Code sienta las bases técnicas."
    ],
    desc:""
  }
};
// ── Utilitaires de base ───────────────────────────────────────────
function t(k){return(T[S.lang]||T[defs.lang]||{})[k]||(T[defs.lang]||{})[k]||k}  // Traduction
function appTitle(){return S.aiName||(titleByLang[S.lang]||titleByLang[defs.lang])}  // Titre localisé (personnalisable)
// ── Met à jour en temps réel le footer de la sidebar (nom + avatar) ──
// Priorité nom   : aiName > prénom+nom utilisateur > titre par défaut
// Priorité logo  : aiLogo > avatar utilisateur > main-logo > initiales
function updateSidebarProfile(){
  try{
    const nameEl=document.getElementById('sidebar-profile-name');
    const avEl=document.getElementById('sidebar-profile-avatar');
    // On lit les deux jeux de clés : onglet "Profil" (profile-*) prioritaire,
    // sinon onglet "Personnalisation" (firstname / lastname).
    const _read=k=>(typeof ls==='function'?(ls(k)||''):'');
    const pFn=_read('profile-firstname').trim();
    const pLn=_read('profile-lastname').trim();
    const fn=(pFn||_read('firstname').trim());
    const ln=(pLn||_read('lastname').trim());
    const userFull=(fn+' '+ln).trim();
    const aiName=((typeof S!=='undefined'&&S&&S.aiName)||'').trim();
    // Priorité : prénom+nom utilisateur > aiName > titre par défaut
    const displayName=userFull||aiName||(typeof appTitle==='function'?appTitle():'Le Goat')||'Le Goat';
    if(nameEl)nameEl.textContent=displayName;
    if(avEl){
      const aiLogo=((typeof S!=='undefined'&&S&&S.aiLogo)||'');
      const userAvatar=_read('profile-avatar');
      const mainLogoEl=document.getElementById('main-logo');
      const mainLogoSrc=mainLogoEl?(mainLogoEl.getAttribute('src')||''):'';
      const src=aiLogo||userAvatar||mainLogoSrc;
      if(src){
        let img=avEl.querySelector('img');
        if(!img){avEl.textContent='';img=document.createElement('img');img.alt='';avEl.appendChild(img)}
        if(img.getAttribute('src')!==src)img.setAttribute('src',src);
      }else{
        if(avEl.querySelector('img'))avEl.innerHTML='';
        const initials=((fn[0]||'')+(ln[0]||'')).toUpperCase()||((displayName[0]||'G').toUpperCase());
        avEl.textContent=initials;
      }
    }
  }catch(e){/* tolère un appel précoce */}
}
function updateAiName(){if(brandText)brandText.textContent=appTitle();if(tabCoworking)tabCoworking.textContent=appTitle()+' Code';updateSidebarProfile();renderMessages()}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;')}  // Échappement HTML

// ── Système audio (Web Audio API, synthèse additive) ─────────────
// Aucun fichier audio externe — les sons sont générés en temps réel.
// Pour ajouter un style sonore, ajoutez un cas dans playClick() / playKey().
function ensureAudio(){if(audioCtx)return audioCtx;const A=window.AudioContext||window.webkitAudioContext;if(!A)return null;audioCtx=new A();return audioCtx}
function tone(f,d,type,g,det){const c=ensureAudio();if(!c)return;if(c.state==='suspended')c.resume().catch(()=>{});const o=c.createOscillator(),a=c.createGain();o.type=type||'sine';o.frequency.value=f;o.detune.value=det||0;const n=c.currentTime;a.gain.setValueAtTime(.0001,n);a.gain.exponentialRampToValueAtTime(g||.1,n+.01);a.gain.exponentialRampToValueAtTime(.0001,n+d);o.connect(a);a.connect(c.destination);o.start(n);o.stop(n+d+.01)}
function playClick(){if(S.clickSound!=='on')return;if(S.clickStyle==='nebrise'){tone(260,.055,'sawtooth',.07);setTimeout(()=>tone(340,.045,'triangle',.05),22);return}tone(420,.06,'triangle',.08)}
function playSend(){if(S.clickSound!=='on')return;tone(600,.045,'sine',.10);setTimeout(()=>tone(820,.055,'sine',.08),35)}
function playAiReply(){if(S.aiSound!=='on')return;tone(520,.06,'sine',.085);setTimeout(()=>tone(680,.05,'sine',.07),40)}
let lastKS=0;function playKey(){if(S.kbSound!=='on')return;const n=performance.now();if(n-lastKS<22)return;lastKS=n;if(S.kbStyle==='aurela'){tone(320,.03,'triangle',.06);return}if(S.kbStyle==='verdrock'){tone(180,.025,'square',.045);return}if(S.kbStyle==='feryn'){tone(520,.02,'sine',.06,-12);setTimeout(()=>tone(520,.02,'sine',.05,14),18);return}tone(560,.02,'sine',.05)}

// ── Tooltips ─────────────────────────────────────────────────────
// Les tooltips sont positionnés dynamiquement pour rester dans la fenêtre.
// Liez un tooltip via bindTip(element, 'tooltip_cle') ou bindTip(element, 'Texte direct').
function showTip(el,txt){tooltipEl.textContent=txt;tooltipEl.hidden=false;const r=el.getBoundingClientRect();tooltipEl.style.top=Math.min(innerHeight-12,r.bottom+10)+'px';tooltipEl.style.left=Math.max(12,Math.min(innerWidth-12,r.left))+'px';requestAnimationFrame(()=>tooltipEl.classList.add('show'))}
function hideTip(){tooltipEl.classList.remove('show');setTimeout(()=>{if(!tooltipEl.classList.contains('show'))tooltipEl.hidden=true},120)}
function bindTip(el,k){if(!el)return;el.addEventListener('mouseenter',()=>{ttTimer=setTimeout(()=>showTip(el,k.startsWith('tooltip_')?t(k):k),520)});el.addEventListener('mouseleave',()=>{clearTimeout(ttTimer);hideTip()});el.addEventListener('mousedown',()=>{clearTimeout(ttTimer);hideTip()})}

// ── Character Counter & Contraction Of Chat ──
const CHAR_LIMIT=10000;
const SHEET_CHAR_LIMIT=14000;
function getTotalSheetChars(){return sheets.reduce((sum,txt)=>sum+txt.length,0)}
function getTotalChars(){return ta.value.length+getTotalSheetChars()}
function updateCharCounter(){const inputLen=ta.value.length;const isOC=S.overclock==='on';charCounterText.textContent=inputLen.toLocaleString('fr')+' / '+(isOC?'∞':'10 000');charCounterEl.classList.remove('warning','danger');if(!isOC&&inputLen>=CHAR_LIMIT){charCounterEl.classList.add('danger')}else if(!isOC&&inputLen>=CHAR_LIMIT*0.8){charCounterEl.classList.add('warning')}else if(isOC&&inputLen>=CHAR_LIMIT){charCounterEl.classList.add('danger')}charCounterTip.textContent=isOC&&inputLen>=CHAR_LIMIT?t('char_limit_overclock_tooltip'):t('char_limit_tooltip');updateContraction()}
function enforceCharLimit(){if(S.overclock==='on')return;if(ta.value.length>CHAR_LIMIT){ta.value=ta.value.substring(0,CHAR_LIMIT);updateCharCounter()}}
function updateContraction(){const total=getTotalChars();const show=total>=CHAR_LIMIT;contractionTag.hidden=!show;contractionTip.textContent=t('contraction_tooltip')}

// ── Overclock system ──
function updateOverclockUI(){overclockToggle.classList.toggle('active',S.overclock==='on');updateCharCounter();updateContraction()}
function openOverclockModal(){ocWarningText.textContent=t('overclock_warning');ocConfirmBtn.textContent=t('overclock_confirm');ocCancelBtn.textContent=t('overclock_cancel');ocBackdrop.classList.add('open')}
function closeOverclockModal(){ocBackdrop.classList.remove('open')}
overclockToggle.addEventListener('click',()=>{playClick();if(S.overclock==='on'){S.overclock='off';ls('overclock','off');updateOverclockUI()}else{openOverclockModal()}});
ocConfirmBtn.addEventListener('click',()=>{playClick();S.overclock='on';ls('overclock','on');closeOverclockModal();updateOverclockUI()});
ocCancelBtn.addEventListener('click',()=>{playClick();closeOverclockModal()});
ocBackdrop.addEventListener('click',e=>{if(e.target===ocBackdrop)closeOverclockModal()});

// ── Stop generation ──
function showStopBtn(){sendBtn.hidden=true;stopBtn.hidden=false;isGenerating=true}
function hideStopBtn(){stopBtn.hidden=true;sendBtn.hidden=false;sendBtn.disabled=false;isGenerating=false;abortController=null}
stopBtn.addEventListener('click',()=>{playClick();if(abortController){abortController.abort()}hideStopBtn();statusEl.textContent=ST[S.lang]||ST[defs.lang]});

// ── Font switching ──
function applyAiFont(v,snd){apply('aifont',['default','arial','opendyslexic'].includes(v)?v:'default','aifont',snd);document.body.dataset.aifont=S.aifont;$$('[data-aifont-value]').forEach(b=>b.classList.toggle('active',b.dataset.aifontValue===S.aifont))}
function applyUserFont(v,snd){apply('userfont',['default','arial','opendyslexic'].includes(v)?v:'default','userfont',snd);document.body.dataset.userfont=S.userfont;$$('[data-userfont-value]').forEach(b=>b.classList.toggle('active',b.dataset.userfontValue===S.userfont))}

// ── Model dropdown (ChatGPT style) ──
// Le bandeau supérieur affiche soit le modèle standard (Sukoshi /
// Traditionnel / Maestro), soit "Custom" lorsqu'un modèle personnalisé
// est actif (cf. section "Modèles personnalisés" plus bas).
function renderModelDD(){
  const customActive=(typeof cmHasCustomActive==='function')&&cmHasCustomActive();
  // Étiquette en haut (à gauche du chevron).
  if(customActive){
    modelCurrentLabel.textContent=t('models_custom_label');
  }else{
    const fallback=models.find(m=>m.id===S.model)||models.find(m=>m.id===defs.model)||models[0];
    if(fallback){if(S.model!==fallback.id){S.model=fallback.id;ls('model',S.model)}modelCurrentLabel.textContent=t(fallback.label_key)}
  }
  // Liste : tous les modèles standards. Si un modèle custom est actif,
  // ils sont visuellement verrouillés et un clic ouvre une alerte.
  modelDDMenu.innerHTML='<div class="model-dd-header">'+esc(t('model_recent'))+'</div>'+models.map(m=>{
    const sel=(!customActive&&m.id===S.model);
    const locked=customActive;
    return '<button type="button" class="model-dd-item'+(sel?' selected':'')+(locked?' locked':'')+'" data-model="'+esc(m.id)+'"'+(locked?' aria-disabled="true"':'')+' role="menuitemradio"><div class="m-info"><span class="m-name">'+esc(t(m.label_key))+'</span><span class="m-desc">'+esc(t(m.desc_key))+'</span></div><span class="m-check">✓</span></button>';
  }).join('')+'<div class="model-dd-sep"></div>';
  modelDDMenu.querySelectorAll('[data-model]').forEach(b=>b.addEventListener('click',()=>{
    playClick();
    if(customActive){
      // Verrou : pour basculer vers Sukoshi/Maestro/Traditionnel,
      // l'utilisateur doit d'abord remettre le modèle sur "Par défaut".
      alert(t('models_default_required'));
      return;
    }
    const nextModel=b.dataset.model;
    if(nextModel===S.model){closeModelDD();return}
    S.model=nextModel;ls('model',S.model);
    enforceMode();renderModelDD();renderModes();updateModeUI();renderStyles();updateStyleUI();renderGadgets();updateGadgetUI();
    if(typeof updateCustomModelTriggerUI==='function')updateCustomModelTriggerUI();
    closeModelDD();refreshWelcomeContent();
    statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);
  }));
}
function openModelDD(){modelDDMenu.classList.add('open');modelTriggerBtn.setAttribute('aria-expanded','true');var tc=$('tab-chat');if(tc)tc.setAttribute('aria-expanded','true')}
function closeModelDD(){modelDDMenu.classList.remove('open');modelTriggerBtn.setAttribute('aria-expanded','false');var tc=$('tab-chat');if(tc)tc.setAttribute('aria-expanded','false')}
modelTriggerBtn.addEventListener('click',()=>{playClick();modelDDMenu.classList.contains('open')?closeModelDD():openModelDD()});

// ── Private Chat (mode incognito) ──
let themeBeforePrivate=null;
function enterPrivateChat(){
  // Si on est dans Goat Code, revenir au chat d'abord
  if(activeTab==='coworking'){activeTab='chat';updateTabUI()}
  S.privateChat=true;
  privateChatBtn.classList.add('active');
  // Désactiver l'onglet Goat Code
  if(tabCoworking){tabCoworking.disabled=true}
  themeBeforePrivate=S.theme;
  document.body.dataset.theme='dark';S.theme='dark';
  $$('[data-theme-value]').forEach(b=>b.classList.toggle('active',b.dataset.themeValue==='dark'));
  updateThemedLogos();
  messages=[];renderMessages();
  welcomeEl.textContent=t('private_chat_welcome');
  welcomeDesc.textContent=t('private_chat_welcome_desc');
  ta.value='';autoResize();
  statusEl.textContent=ST[S.lang]||ST[defs.lang];
  fetch('/api/new_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})}).catch(()=>{})
}
function exitPrivateChat(){
  S.privateChat=false;
  privateChatBtn.classList.remove('active');
  // Réactiver l'onglet Goat Code
  if(tabCoworking){tabCoworking.disabled=false}
  const restore=themeBeforePrivate||defs.theme;
  themeBeforePrivate=null;
  applyTheme(restore,false);
  refreshWelcomeContent()
}
privateChatBtn.addEventListener('click',()=>{playClick();S.privateChat?exitPrivateChat():enterPrivateChat()});
function updatePrivateChatLabels(){$('pc-title').textContent=t('private_chat');$('pc-desc').textContent=t('private_chat_desc')}

// ── Modes ──
function isModeOff(id){return S.optResp==='on'&&DM.includes(id)}
function isStyleOff(){return false}
function enforceMode(){if(S.mode&&isModeOff(S.mode)){S.mode='fast';ls('mode',S.mode)}if(S.wstyle&&isStyleOff()){S.wstyle='';ls('wstyle',S.wstyle)}}
function updateModeUI(){enforceMode();const m=MO.find(o=>o.id===S.mode);modeLbl.textContent=m?t('mode_'+m.id):t('no_mode');modeIcn.textContent=m?m.icon:'○';modeAnn.textContent=m?t('mode_active_prefix')+' '+t('mode_'+m.id):''}
function renderModes(){modeMenu.innerHTML=MO.map(o=>{const sel=o.id===S.mode,dis=isModeOff(o.id);return'<button type="button" class="dropdown-menu-item'+(sel?' selected':'')+(dis?' disabled':'')+'" data-mode-id="'+esc(o.id)+'" '+(dis?'disabled':'')+' role="menuitemradio"><span class="dm-icon">'+esc(o.icon)+'</span><span class="dm-label">'+esc(t('mode_'+o.id))+'</span><span class="dm-check">✓</span></button>'}).join('');modeMenu.querySelectorAll('[data-mode-id]').forEach(b=>{bindTip(b,'tooltip_mode_'+b.dataset.modeId);b.addEventListener('click',()=>{if(b.disabled)return;playClick();S.mode=(b.dataset.modeId===S.mode)?'':b.dataset.modeId;ls('mode',S.mode);renderModes();updateModeUI();closeMM()})})}
function openMM(){modeMenu.classList.add('open');modeTrigger.setAttribute('aria-expanded','true')}
function closeMM(){modeMenu.classList.remove('open');modeTrigger.setAttribute('aria-expanded','false')}

// ── Writing Styles ──
function updateStyleUI(){const s=wStyles.find(o=>o.id===S.wstyle);styleLbl.textContent=s?t('style_'+s.id):t('writing_style_label');styleIcn.textContent=s?s.icon:'✎'}
function renderStyles(){const blocked=isStyleOff();styleMenu.innerHTML=wStyles.map(o=>{const sel=o.id===S.wstyle;return'<button type="button" class="dropdown-menu-item'+(sel?' selected':'')+(blocked?' disabled':'')+'" data-style-id="'+esc(o.id)+'" '+(blocked?'disabled':'')+' role="menuitemradio"><span class="dm-icon">'+esc(o.icon)+'</span><span class="dm-label">'+esc(t('style_'+o.id))+'</span><span class="dm-check">✓</span></button>'}).join('');styleMenu.querySelectorAll('[data-style-id]').forEach(b=>{bindTip(b,'tooltip_style_'+b.dataset.styleId);b.addEventListener('click',()=>{if(b.disabled)return;playClick();S.wstyle=(b.dataset.styleId===S.wstyle)?'':b.dataset.styleId;ls('wstyle',S.wstyle);renderStyles();updateStyleUI();closeSM()})})}
function openSM(){styleMenu.classList.add('open');styleTrigger.setAttribute('aria-expanded','true')}
function closeSM(){styleMenu.classList.remove('open');styleTrigger.setAttribute('aria-expanded','false')}

/* ── Gadgets (desactive pour le moment) ──
function updateGadgetUI(){const g=gadgets.find(o=>o.id===S.gadget);gadgetLbl.textContent=g?t('gadget_'+g.id):t('gadget_label');gadgetIcn.textContent=g?g.icon:'⚙'}
function renderGadgets(){gadgetMenu.innerHTML=gadgets.map(o=>{const sel=o.id===S.gadget;return'<button type="button" class="dropdown-menu-item'+(sel?' selected':'')+'" data-gadget-id="'+esc(o.id)+'" role="menuitemradio"><span class="dm-icon">'+esc(o.icon)+'</span><span class="dm-label">'+esc(t('gadget_'+o.id))+'</span><span class="dm-check">✓</span></button>'}).join('');gadgetMenu.querySelectorAll('[data-gadget-id]').forEach(b=>{bindTip(b,'tooltip_gadget_'+b.dataset.gadgetId);b.addEventListener('click',()=>{playClick();S.gadget=(b.dataset.gadgetId===S.gadget)?'':b.dataset.gadgetId;ls('gadget',S.gadget);renderGadgets();updateGadgetUI();closeGM()})})}
function openGM(){gadgetMenu.classList.add('open');gadgetTrigger.setAttribute('aria-expanded','true')}
function closeGM(){gadgetMenu.classList.remove('open');gadgetTrigger.setAttribute('aria-expanded','false')}
*/
function updateGadgetUI(){}
function renderGadgets(){}
function openGM(){}
function closeGM(){}

// =================================================================
// ── Modèles personnalisés ─────────────────────────────────────────
// =================================================================
// Activé via Settings → Personnalisation → "Autres modèles".
// Lorsque actif, un bouton "Modèles" apparaît à côté du sélecteur
// de style d'écriture. Il permet d'ajouter / renommer / supprimer
// des modèles personnalisés. Sélectionner un modèle custom remplace
// l'étiquette du bandeau supérieur ("Traditionnel" → "Custom") et
// verrouille les modèles d'origine jusqu'à ce que l'utilisateur
// remette le modèle sur "Par défaut" via le menu modèle du haut.
// -----------------------------------------------------------------

// État utilitaires —
function cmGenId(){return 'cm-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,7)}
function cmSave(){ls('custom-models',JSON.stringify(S.customModels||[]))}
function cmGet(id){return (S.customModels||[]).find(m=>m.id===id)||null}
function cmHasCustomActive(){return !!(S.activeCustomModel&&cmGet(S.activeCustomModel))}
function cmTrimName(s){return String(s||'').trim().slice(0,64)}
function cmNameTaken(name,exceptId){const n=name.toLowerCase();return (S.customModels||[]).some(m=>m.id!==exceptId&&String(m.name).toLowerCase()===n)}

// Affiche/masque le bouton "Modèles" selon l'état de l'interrupteur.
function applyOtherModelsOn(v,snd){
  apply('otherModelsOn',v==='on'?'on':'off','other-models-on',snd);
  if(otherModelsToggle)otherModelsToggle.checked=(S.otherModelsOn==='on');
  if(customModelsPanel)customModelsPanel.hidden=(S.otherModelsOn!=='on');
  // Si désactivé : on ferme le menu et on retombe sur le modèle par défaut.
  if(S.otherModelsOn!=='on'){
    closeCustomModelsMenu();
    if(cmHasCustomActive()){
      S.activeCustomModel='';ls('active-custom-model','');
      S.model=defs.model;ls('model',S.model);
      renderModelDD();
    }
  }
  renderCustomModelsMenu();
  updateCustomModelTriggerUI();
}

// Met à jour l'icône + libellé du bouton "Modèles" (affiche le nom du
// modèle actif s'il y en a un, sinon le libellé générique).
function updateCustomModelTriggerUI(){
  if(!customModelsLabel)return;
  const active=cmHasCustomActive()?cmGet(S.activeCustomModel):null;
  customModelsLabel.textContent=active?active.name:t('models_btn_label');
  const icon=$('custom-models-icon');
  if(icon)icon.textContent=active?'✦':'⚙';
  if(customModelsTrigger)customModelsTrigger.classList.toggle('active',!!active);
}

// Rend le contenu du menu déroulant "Modèles".
function renderCustomModelsMenu(){
  if(!customModelsMenu)return;
  const list=S.customModels||[];
  let html='';
  if(cmHasCustomActive()){
    html+='<button type="button" class="custom-models-default-btn" id="cm-set-default-btn">'+esc(t('models_set_default'))+'</button>';
    html+='<div class="custom-models-sep"></div>';
  }
  if(!list.length){
    html+='<div class="custom-models-empty">'+esc(t('models_no_custom'))+'</div>';
  }else{
    html+=list.map(m=>{
      const sel=(S.activeCustomModel===m.id);
      return '<div class="custom-model-row'+(sel?' selected':'')+'" data-cm-id="'+esc(m.id)+'" role="menuitemradio">'+
        '<span class="cmr-name">'+esc(m.name)+'</span>'+
        '<span class="cmr-actions">'+
          '<button type="button" class="cmr-act-btn" data-cm-action="rename" data-cm-id="'+esc(m.id)+'" title="'+esc(t('models_rename'))+'" aria-label="'+esc(t('models_rename'))+'">✎</button>'+
          '<button type="button" class="cmr-act-btn" data-cm-action="delete" data-cm-id="'+esc(m.id)+'" title="'+esc(t('models_delete'))+'" aria-label="'+esc(t('models_delete'))+'">🗑</button>'+
        '</span>'+
      '</div>';
    }).join('');
  }
  html+='<button type="button" class="custom-models-add-btn" id="cm-add-btn">+ '+esc(t('models_add'))+'</button>';
  customModelsMenu.innerHTML=html;

  // Ajout
  const addBtn=$('cm-add-btn');
  if(addBtn)addBtn.addEventListener('click',e=>{e.stopPropagation();playClick();openCustomModelModal('add')});
  // Reset par défaut
  const resetBtn=$('cm-set-default-btn');
  if(resetBtn)resetBtn.addEventListener('click',e=>{e.stopPropagation();playClick();resetActiveCustomModel()});
  // Sélection / actions
  customModelsMenu.querySelectorAll('[data-cm-action]').forEach(btn=>{
    btn.addEventListener('click',e=>{
      e.stopPropagation();playClick();
      const id=btn.dataset.cmId,act=btn.dataset.cmAction;
      if(act==='rename')openCustomModelModal('rename',id);
      else if(act==='delete')deleteCustomModel(id);
    });
  });
  customModelsMenu.querySelectorAll('.custom-model-row').forEach(row=>{
    row.addEventListener('click',e=>{
      if(e.target.closest('[data-cm-action]'))return;
      playClick();selectCustomModel(row.dataset.cmId);
    });
  });
}

function openCustomModelsMenu(){if(!customModelsMenu)return;customModelsMenu.classList.add('open');if(customModelsTrigger)customModelsTrigger.setAttribute('aria-expanded','true')}
function closeCustomModelsMenu(){if(!customModelsMenu)return;customModelsMenu.classList.remove('open');if(customModelsTrigger)customModelsTrigger.setAttribute('aria-expanded','false')}

// Sélection d'un modèle custom : pose le sentinel sur S.model et
// l'id réel sur S.activeCustomModel. Re-cliquer déselectionne.
function selectCustomModel(id){
  const m=cmGet(id);if(!m)return;
  if(S.activeCustomModel===id){
    resetActiveCustomModel();
    return;
  }
  S.activeCustomModel=id;ls('active-custom-model',id);
  S.model=CUSTOM_MODEL_SENTINEL;ls('model',S.model);
  enforceMode();renderModelDD();renderModes();updateModeUI();renderStyles();updateStyleUI();
  renderCustomModelsMenu();updateCustomModelTriggerUI();
  closeCustomModelsMenu();
  refreshWelcomeContent();
}

// Remet le modèle sur le défaut (sortie du mode "custom").
function resetActiveCustomModel(){
  S.activeCustomModel='';ls('active-custom-model','');
  S.model=defs.model;ls('model',S.model);
  enforceMode();renderModelDD();renderModes();updateModeUI();renderStyles();updateStyleUI();
  renderCustomModelsMenu();updateCustomModelTriggerUI();
  refreshWelcomeContent();
}

// ── Modale "NAME Models" ─────────────────────────────────────
let customModelEditTarget=null;   // 'add' | id-en-cours-de-renommage
function openCustomModelModal(mode,id){
  customModelEditTarget=(mode==='rename'&&id)?id:'add';
  if(customModelTitleEl)customModelTitleEl.textContent=t('models_modal_title');
  customModelInput.value=(mode==='rename')?(cmGet(id)?cmGet(id).name:''):'';
  customModelErrorEl.hidden=true;customModelErrorEl.textContent='';
  customModelBackdrop.classList.add('open');
  setTimeout(()=>{customModelInput.focus();customModelInput.select()},40);
}
function closeCustomModelModal(){customModelBackdrop.classList.remove('open');customModelEditTarget=null}

function submitCustomModelModal(){
  const name=cmTrimName(customModelInput.value);
  if(!name){customModelErrorEl.textContent=t('models_invalid_name');customModelErrorEl.hidden=false;return}
  const editingId=(customModelEditTarget&&customModelEditTarget!=='add')?customModelEditTarget:null;
  if(cmNameTaken(name,editingId)){customModelErrorEl.textContent=t('models_duplicate_name');customModelErrorEl.hidden=false;return}
  if(editingId){
    const m=cmGet(editingId);if(m)m.name=name;
  }else{
    const newModel={id:cmGenId(),name:name};
    S.customModels.push(newModel);
  }
  cmSave();
  renderCustomModelsMenu();updateCustomModelTriggerUI();
  closeCustomModelModal();
}

function deleteCustomModel(id){
  if(!confirm(t('models_delete_confirm')))return;
  const list=S.customModels||[];
  S.customModels=list.filter(m=>m.id!==id);
  cmSave();
  if(S.activeCustomModel===id){
    // Le modèle actif vient d'être supprimé : on retombe sur le défaut.
    resetActiveCustomModel();
  }else{
    renderCustomModelsMenu();updateCustomModelTriggerUI();
  }
}

// Hook d'événements (déclenchés une seule fois au chargement).
if(otherModelsToggle){otherModelsToggle.addEventListener('change',()=>{playClick();applyOtherModelsOn(otherModelsToggle.checked?'on':'off')})}
if(customModelsTrigger){customModelsTrigger.addEventListener('click',e=>{e.stopPropagation();playClick();customModelsMenu.classList.contains('open')?closeCustomModelsMenu():openCustomModelsMenu()})}
if(customModelEnterBtn){customModelEnterBtn.addEventListener('click',submitCustomModelModal)}
if(customModelCancelBtn){customModelCancelBtn.addEventListener('click',closeCustomModelModal)}
if(customModelBackdrop){customModelBackdrop.addEventListener('click',e=>{if(e.target===customModelBackdrop)closeCustomModelModal()})}
if(customModelInput){customModelInput.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();submitCustomModelModal()}else if(e.key==='Escape'){e.preventDefault();closeCustomModelModal()}})}
// Fermer le menu déroulant lorsqu'on clique en dehors.
document.addEventListener('click',e=>{
  if(!customModelsMenu||!customModelsMenu.classList.contains('open'))return;
  if(customModelsMenu.contains(e.target)||(customModelsTrigger&&customModelsTrigger.contains(e.target)))return;
  closeCustomModelsMenu();
});

// ── Migration modal ──
function openMigrate(){migrateTitle.textContent=t('migrate_title');migrateStep1.textContent=t('migrate_step1');migrateStep2.textContent=t('migrate_step2');migratePromptBox.textContent=migrationPrompt;migrateTA.value='';migrateTA.placeholder=t('migrate_paste_placeholder');migrateAddBtn.textContent=t('migrate_add');migrateCancelBtn.textContent=t('migrate_cancel');migrateAddBtn.disabled=true;migrateBackdrop.classList.add('open')}
function closeMigrate(){migrateBackdrop.classList.remove('open')}
migrateTA.addEventListener('input',()=>{migrateAddBtn.disabled=!migrateTA.value.trim()});
migrateAddBtn.addEventListener('click',()=>{closeMigrate();alert(t('migrate_success'))});
migrateCancelBtn.addEventListener('click',closeMigrate);
migrateCloseX.addEventListener('click',closeMigrate);
migrateBackdrop.addEventListener('click',e=>{if(e.target===migrateBackdrop)closeMigrate()});
// Copy button inside prompt box
migratePromptBox.insertAdjacentHTML('afterend','');
document.addEventListener('click',e=>{if(e.target&&e.target.id==='migrate-copy-btn'){const tx=migrationPrompt;navigator.clipboard.writeText(tx).then(()=>{e.target.textContent='✓'}).catch(()=>{});setTimeout(()=>{if(e.target)e.target.textContent=t('migrate_copy')},1500)}});

// ── Messages ──
// ── Sheets system ──
function renderSheets(){sheetsRow.innerHTML=sheets.map((txt,i)=>'<div class="sheet-thumb"><span>'+esc(txt.substring(0,80))+'</span><button type="button" class="sheet-remove" data-sheet-idx="'+i+'">×</button></div>').join('');sheetsRow.querySelectorAll('.sheet-remove').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();sheets.splice(+b.dataset.sheetIdx,1);renderSheets();updateCharCounter()}));updateContraction()}
function openSheetModal(){sheetTitle.textContent=t('sheet_title');sheetAddBtn.textContent=t('sheet_add');sheetCancelBtn.textContent=t('sheet_cancel');sheetTA.value='';updateSheetCharCounter();sheetBackdrop.classList.add('open')}
function closeSheetModal(){sheetBackdrop.classList.remove('open')}
function updateSheetCharCounter(){const len=sheetTA.value.length;const isOC=S.overclock==='on';sheetCharCounter.textContent=len.toLocaleString('fr')+' / '+(isOC?'∞':'14 000');sheetCharCounter.classList.toggle('danger',!isOC&&len>=SHEET_CHAR_LIMIT)}
function enforceSheetCharLimit(){if(S.overclock==='on')return;if(sheetTA.value.length>SHEET_CHAR_LIMIT){sheetTA.value=sheetTA.value.substring(0,SHEET_CHAR_LIMIT);updateSheetCharCounter()}}
sheetTA.addEventListener('input',()=>{enforceSheetCharLimit();updateSheetCharCounter()});
sheetAddBtn.addEventListener('click',()=>{const v=sheetTA.value.trim();if(!v)return;const maxSheets=S.overclock==='on'?10:1;if(sheets.length>=maxSheets){alert(S.overclock==='on'?t('sheets_max'):t('sheets_max_one'));return}if(S.overclock!=='on'&&v.length>SHEET_CHAR_LIMIT){return}sheets.push(v);renderSheets();closeSheetModal();updateCharCounter()});
sheetCancelBtn.addEventListener('click',closeSheetModal);
sheetBackdrop.addEventListener('click',e=>{if(e.target===sheetBackdrop)closeSheetModal()});
composerPlus.addEventListener('click',()=>{playClick();plusMenu.classList.toggle('open')});
plusAddSheet.addEventListener('click',()=>{playClick();plusMenu.classList.remove('open');openSheetModal()});

// ── Messages (with Goat Code buttons) ──
function shouldShowProfileAvatarInMessages(){return profileGet('showMessageAvatar','off')==='on'}
function getProfileAvatarForMessages(){return profileGet('avatar','')||($('main-logo')?$('main-logo').getAttribute('src'):'')}
function showProfileAvatarHover(target){if(!profileAvatarHoverCard||!profileAvatarHoverImage||!profileAvatarHoverName||!profileAvatarHoverBio)return;const data=getProfileData();const src=data.avatar||getProfileAvatarForMessages();if(!src)return;profileAvatarHoverImage.src=src;applyAvatarFitMode(profileAvatarHoverImage,src);profileAvatarHoverName.textContent=getProfileFullName(data);profileAvatarHoverBio.textContent=(data.bio||t('profile_preview_title'));if(profileAvatarHoverBanner)profileAvatarHoverBanner.style.backgroundImage=data.banner?'url("'+String(data.banner).replace(/"/g,'\"')+'")':'';const rect=target.getBoundingClientRect();const cardW=288,cardH=178;let left=rect.left-cardW+rect.width;if(left<12)left=Math.min(window.innerWidth-cardW-12,rect.right+10);let top=rect.top-(cardH-rect.height)/2;top=Math.max(12,Math.min(window.innerHeight-cardH-12,top));profileAvatarHoverCard.hidden=false;profileAvatarHoverCard.style.left=left+'px';profileAvatarHoverCard.style.top=top+'px';requestAnimationFrame(()=>profileAvatarHoverCard.classList.add('show'))}
function hideProfileAvatarHover(immediate){clearTimeout(avatarHoverTimer);if(!profileAvatarHoverCard)return;if(immediate){profileAvatarHoverCard.classList.remove('show');profileAvatarHoverCard.hidden=true;return}profileAvatarHoverCard.classList.remove('show');setTimeout(()=>{if(profileAvatarHoverCard&&!profileAvatarHoverCard.classList.contains('show'))profileAvatarHoverCard.hidden=true},160)}
function bindUserAvatarHover(scope){if(!scope)return;scope.querySelectorAll('.message-user-avatar').forEach(el=>{el.addEventListener('mouseenter',()=>{clearTimeout(avatarHoverTimer);avatarHoverTimer=setTimeout(()=>showProfileAvatarHover(el),500)});el.addEventListener('mouseleave',()=>hideProfileAvatarHover(false))})}

// ── Helpers « Spécificité » ──────────────────────────────────────────────
// Ces fonctions formatent les méta-données associées à chaque réponse IA
// (mode, style, modèle, pièces jointes, horodatage, durée) pour les afficher
// dans le panneau dépliant sous chaque bulle assistant.

// Convertit un timestamp Python (secondes depuis epoch, float) en chaîne
// localisée du type "08/05/2026 14:32:18". Retourne '' si invalide.
function formatSpecTimestamp(ts){
  if(typeof ts!=='number'||!isFinite(ts)||ts<=0)return '';
  const d=new Date(ts*1000);
  if(isNaN(d.getTime()))return '';
  const lang=({fr:'fr-FR',en:'en-US',es:'es-ES'})[S.lang]||'fr-FR';
  try{
    return d.toLocaleString(lang,{
      year:'numeric',month:'2-digit',day:'2-digit',
      hour:'2-digit',minute:'2-digit',second:'2-digit'
    });
  }catch(e){return d.toISOString()}
}

// Formate une durée en millisecondes au format "1.42 s" ou "850 ms".
function formatSpecDuration(ms){
  if(typeof ms!=='number'||!isFinite(ms)||ms<0)return '';
  if(ms>=1000)return (ms/1000).toFixed(2).replace(/\.?0+$/,'')+' '+t('specificity_seconds_short');
  return Math.round(ms)+' '+t('specificity_milliseconds_short');
}

// Convertit une taille en octets en chaîne lisible (B / KB / MB).
function formatSpecSize(bytes){
  const n=Number(bytes)||0;
  if(n<=0)return '';
  if(n<1024)return n+' B';
  if(n<1024*1024)return (n/1024).toFixed(1).replace(/\.0$/,'')+' KB';
  return (n/(1024*1024)).toFixed(2).replace(/\.?0+$/,'')+' MB';
}

// Résolution id → libellé humain (réutilise les traductions existantes).
function resolveModeLabel(id){
  if(!id)return '';
  const opt=(MO||[]).find(m=>m&&m.id===id);
  if(opt){const k='mode_'+opt.id;const tr=t(k);if(tr&&tr!==k)return tr}
  const k='mode_'+id;const tr=t(k);return (tr&&tr!==k)?tr:id;
}
function resolveStyleLabel(id){
  if(!id)return '';
  const k='style_'+id;const tr=t(k);return (tr&&tr!==k)?tr:id;
}
function resolveModelLabel(meta){
  if(!meta)return '';
  // Modèle personnalisé saisi par l'utilisateur (ex. "mistral small 4 bas").
  if(meta.custom_model_name)return meta.custom_model_name;
  if(meta.model===CUSTOM_MODEL_SENTINEL){return t('specificity_custom_model')}
  if(!meta.model)return '';
  const opt=(models||[]).find(m=>m&&m.id===meta.model);
  if(opt&&opt.label_key){const tr=t(opt.label_key);if(tr&&tr!==opt.label_key)return tr}
  const k='model_'+meta.model;const tr=t(k);return (tr&&tr!==k)?tr:meta.model;
}

// Construit le HTML d'une ligne du panneau (label + valeur, ou état "vide").
function buildSpecRow(labelKey,value,muted){
  const v=(value===undefined||value===null||value==='')
    ? '<span class="specificity-value is-muted">'+esc(t('specificity_none'))+'</span>'
    : '<span class="specificity-value'+(muted?' is-muted':'')+'">'+value+'</span>';
  return '<div class="specificity-label">'+esc(t(labelKey))+'</div>'+v;
}

// Construit la liste HTML des pièces jointes pour le panneau.
function buildSpecAttachments(list){
  if(!Array.isArray(list)||list.length===0){
    return '<span class="specificity-value is-muted">'+esc(t('specificity_no_attachments'))+'</span>';
  }
  const items=list.map(a=>{
    const kind=esc((a&&a.kind)||'file');
    const name=esc((a&&a.name)||'-');
    const size=formatSpecSize(a&&a.size);
    return '<div class="specificity-attachment">'
      +'<span class="specificity-attachment-kind">'+kind+'</span>'
      +'<span class="specificity-attachment-name">'+name+'</span>'
      +(size?'<span class="specificity-attachment-size">'+esc(size)+'</span>':'')
      +'</div>';
  }).join('');
  return '<div class="specificity-attachments">'+items+'</div>';
}

// Construit le HTML du panneau dépliant pour un message assistant donné.
function buildSpecPanel(meta,idx){
  const isOpen=openSpecificityPanels.has(idx);
  if(!meta||meta.role!=='assistant'){
    return '<div class="specificity-panel'+(isOpen?' open':'')+'" data-spec-index="'+idx+'">'
      +'<p class="specificity-panel-title">'+esc(t('specificity_title'))+'</p>'
      +'<div class="specificity-value is-muted">'+esc(t('specificity_unavailable'))+'</div>'
      +'</div>';
  }
  const modeLabel  = resolveModeLabel(meta.mode);
  const styleLabel = resolveStyleLabel(meta.style);
  const modelLabel = resolveModelLabel(meta);
  const reqTime    = formatSpecTimestamp(meta.request_ts);
  const resTime    = formatSpecTimestamp(meta.response_ts);
  const dur        = formatSpecDuration(meta.duration_ms);
  let html='<div class="specificity-panel'+(isOpen?' open':'')+'" data-spec-index="'+idx+'">';
  html+='<p class="specificity-panel-title">'+esc(t('specificity_title'))+'</p>';
  html+='<div class="specificity-grid">';
  html+=buildSpecRow('specificity_mode',         modeLabel ?esc(modeLabel) :'');
  html+=buildSpecRow('specificity_style',        styleLabel?esc(styleLabel):'');
  html+=buildSpecRow('specificity_model',        modelLabel?esc(modelLabel):'');
  html+='<div class="specificity-label">'+esc(t('specificity_attachments'))+'</div>';
  html+=buildSpecAttachments(meta.attachments);
  html+=buildSpecRow('specificity_request_time', reqTime?esc(reqTime):'');
  html+=buildSpecRow('specificity_response_time',resTime?esc(resTime):'');
  html+=buildSpecRow('specificity_duration',     dur?esc(dur):'');
  html+='</div></div>';
  return html;
}

// Bascule l'affichage du panneau « Spécificité » pour le message d'index `idx`.
// On modifie uniquement la ligne concernée (pas de full re-render) afin de
// préserver la position de scroll et l'état des autres panneaux.
function toggleSpecificityPanel(idx){
  if(openSpecificityPanels.has(idx))openSpecificityPanels.delete(idx);
  else openSpecificityPanels.add(idx);
  const panel=msgBox.querySelector('.specificity-panel[data-spec-index="'+idx+'"]');
  if(panel)panel.classList.toggle('open',openSpecificityPanels.has(idx));
  const btn=msgBox.querySelector('.bubble-action[data-action="specificity"][data-msg-index="'+idx+'"]');
  if(btn)btn.classList.toggle('is-active',openSpecificityPanels.has(idx));
}

function renderMessages(){const last=messages.length-1;const dotsHtml='<div class="typing-dots"><span></span><span></span><span></span></div>';const isCode=activeTab==='coworking';const showUserAvatar=shouldShowProfileAvatarInMessages();const userAvatar=getProfileAvatarForMessages();msgBox.innerHTML=messages.map(([s,txt],i)=>{const e=esc(txt);const isLoading=txt==='\u2026';if(s!=='Vous'){
      // ── Bulle assistant ────────────────────────────────────────────
      let acts='';
      if(!isLoading){
        // Le bouton « Spécificité » est visible sur toutes les réponses IA
        // afin de pouvoir consulter rétrospectivement le contexte d'une
        // réponse, même après plusieurs envois.
        acts='<div class="bubble-actions">';
        acts+='<button type="button" class="bubble-action'+(openSpecificityPanels.has(i)?' is-active':'')+'" data-action="specificity" data-tooltip-key="tooltip_specificity" data-msg-index="'+i+'" aria-expanded="'+(openSpecificityPanels.has(i)?'true':'false')+'">'+esc(t('specificity'))+'</button>';
        // Les actions « Relancer / Relire / Analyser / Exécuter » ne
        // s'appliquent qu'à la dernière réponse pour éviter les régressions
        // (modifier une réponse intermédiaire briserait l'historique).
        if(i===last){
          acts+='<button type="button" class="bubble-action" data-action="regenerate" data-tooltip-key="tooltip_regenerate">'+esc(t('regenerate'))+'</button>';
          if(isCode){
            acts+='<button type="button" class="bubble-action" data-action="review">'+esc(t('review_code'))+'</button>';
            acts+='<button type="button" class="bubble-action" data-action="analyze">'+esc(t('analyze_code'))+'</button>';
            acts+='<button type="button" class="bubble-action" data-action="execute" data-tooltip-key="tooltip_execute_code">'+esc(t('execute_code'))+'</button>';
          }
        }
        acts+='</div>';
      }
      const panelHtml=isLoading?'':buildSpecPanel((messagesMeta||[])[i],i);
      return '<div class="message-row assistant"><div class="bubble">'+(isLoading?dotsHtml:e)+'</div>'+acts+panelHtml+'</div>';
    }const avatarHtml=showUserAvatar&&userAvatar?'<div class="message-user-avatar"><img class="'+(isLogoStyleAvatarSrc(userAvatar)?'is-logo':'')+'" src="'+esc(userAvatar)+'" alt="Photo utilisateur"></div>':'';return'<div class="message-row user"><div class="bubble">'+e+'</div>'+avatarHtml+'</div>'}).join('');shell.classList.toggle('has-messages',messages.length>0);msgBox.scrollTop=msgBox.scrollHeight;bindUserAvatarHover(msgBox);
  // ── Bouton « Spécificité » : toggle du panneau associé ───────────
  msgBox.querySelectorAll('[data-action="specificity"]').forEach(b=>{
    bindTip(b,'tooltip_specificity');
    b.addEventListener('click',()=>{
      playClick();
      const idx=parseInt(b.dataset.msgIndex,10);
      if(!isFinite(idx))return;
      toggleSpecificityPanel(idx);
      b.setAttribute('aria-expanded',openSpecificityPanels.has(idx)?'true':'false');
    });
  });
  msgBox.querySelectorAll('[data-action="regenerate"]').forEach(b=>{bindTip(b,'tooltip_regenerate');b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';showStopBtn();abortController=new AbortController();try{const p=await apiSend(t('regenerate_command'),abortController.signal);messages=p.messages;messagesMeta=p.metas||[];renderMessages();runAiTypingEffect();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){if(e.name!=='AbortError')statusEl.textContent=e.message}finally{hideStopBtn()}})});msgBox.querySelectorAll('[data-action="review"]').forEach(b=>b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';try{const p=await apiSend('Relis et vérifie le code que tu viens de générer.');messages=p.messages;messagesMeta=p.metas||[];renderMessages();runAiTypingEffect();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){statusEl.textContent=e.message}}));msgBox.querySelectorAll('[data-action="analyze"]').forEach(b=>b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';try{const p=await apiSend('Analyse en détail le code que tu viens de générer : structure, complexité, points forts et points faibles.');messages=p.messages;messagesMeta=p.metas||[];renderMessages();runAiTypingEffect();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){statusEl.textContent=e.message}}));msgBox.querySelectorAll('[data-action="execute"]').forEach(b=>{bindTip(b,'tooltip_execute_code');b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';try{const p=await apiSend('Exécute en simulation le code que tu viens de générer et dis-moi si il devrait fonctionner correctement.');messages=p.messages;messagesMeta=p.metas||[];renderMessages();runAiTypingEffect();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){statusEl.textContent=e.message}})})}
let resizeRAF=null;function autoResize(){if(resizeRAF)cancelAnimationFrame(resizeRAF);resizeRAF=requestAnimationFrame(()=>{ta.style.height='auto';ta.style.height=Math.min(ta.scrollHeight,180)+'px'})}

// ── Settings ──
function resetModal(){modal.style.left='50%';modal.style.top='50%';modal.style.transform='translate(-50%,-50%)'}
function openSettings(){playClick();if(settingsOpen)return;settingsOpen=true;resetModal();backdrop.hidden=false;modal.hidden=false;requestAnimationFrame(()=>{backdrop.classList.add('open');modal.classList.add('open')})}
function closeSettings(){playClick();if(!settingsOpen)return;settingsOpen=false;backdrop.classList.remove('open');modal.classList.remove('open');setTimeout(()=>{if(!settingsOpen){backdrop.hidden=true;modal.hidden=true;resetModal()}},180)}
function showTab(id){const section=id||'general';ls('settings-tab',section);$$('[data-settings-tab]').forEach(t=>t.classList.toggle('active',t.dataset.settingsTab===section));$$('[data-settings-content]').forEach(s=>s.classList.toggle('active',s.dataset.settingsContent===section));const content=$('settings-content');if(content)content.scrollTop=0}
function startDrag(e){if(innerWidth<=900)return;if(e.target.closest('button'))return;const r=modal.getBoundingClientRect();modal.style.left=r.left+'px';modal.style.top=r.top+'px';modal.style.transform='none';dragging=true;dragSX=e.clientX;dragSY=e.clientY;mSL=r.left;mST=r.top;e.preventDefault()}
function onDrag(e){if(!dragging)return;modal.style.left=Math.max(12,mSL+(e.clientX-dragSX))+'px';modal.style.top=Math.max(12,mST+(e.clientY-dragSY))+'px'}

// ── Apply settings (UI opt auto-disable quand on réactive un son) ──
function apply(key,val,lsKey,sound){if(sound!==false)playClick();S[key]=val;ls(lsKey||key,val)}
function checkUiOptOff(){if(S.uiOpt==='on'){S.uiOpt='off';ls('uiopt','off');updatePerf()}}
function applyLang(l,snd){apply('lang',['fr','en','es'].includes(l)?l:defs.lang,'lang',snd);document.documentElement.lang=S.lang;$$('[data-language-value]').forEach(b=>b.classList.toggle('active',b.dataset.languageValue===S.lang));applyTranslations()}
function updateThemedLogos(){const isDark=S.theme==='dark';const mainLogo=$('main-logo');if(mainLogo){if(S.aiLogo){mainLogo.src=S.aiLogo}else{const isCowork=activeTab==='coworking';if(isCowork){mainLogo.src=isDark?(mainLogo.dataset.pixelDark||mainLogo.dataset.dark):(mainLogo.dataset.pixelLight||mainLogo.dataset.light)}else{mainLogo.src=isDark?mainLogo.dataset.dark:mainLogo.dataset.light}}}const goatLogo=$('goatistique-logo');if(goatLogo)goatLogo.src=isDark?goatLogo.dataset.dark:goatLogo.dataset.light;const sbMark=document.getElementById('sidebar-brand-mark');const sbMarkImg=document.getElementById('sidebar-brand-mark-img');if(sbMarkImg&&mainLogo){let src='';if(S.aiLogo){src=S.aiLogo}else{src=isDark?(mainLogo.dataset.dark||mainLogo.getAttribute('src')||''):(mainLogo.dataset.light||mainLogo.getAttribute('src')||'')}sbMarkImg.setAttribute('src',src||'');if(sbMark)sbMark.classList.toggle('has-logo',!!src)}updateSidebarProfile()}
function applyTheme(v,snd){if(S.privateChat)return;apply('theme',v==='dark'?'dark':'light','theme',snd);document.body.dataset.theme=S.theme;$$('[data-theme-value]').forEach(b=>b.classList.toggle('active',b.dataset.themeValue===S.theme));updateThemedLogos()}
function applyEffects(v,snd){apply('effects',v==='off'?'off':'on','effects',snd);document.body.dataset.effects=S.effects;updatePerf()}
function applyTextSize(v,snd){apply('textSize',v==='large'?'large':'default','textsize',snd);document.body.dataset.textsize=S.textSize;$$('[data-textsize-value]').forEach(b=>b.classList.toggle('active',b.dataset.textsizeValue===S.textSize))}
function normalizeUIScale(v){const n=parseInt(v,10)||100;return Math.max(70,Math.min(130,n))}
function updateUIScaleUI(){S.uiScale=normalizeUIScale(S.uiScale);if(uiScaleValue)uiScaleValue.textContent=S.uiScale+'%';const scale=S.uiScale/100;document.documentElement.style.setProperty('--ui-scale-factor',String(scale));document.documentElement.style.fontSize='';document.body.style.zoom=String(scale);document.body.style.transformOrigin='top center';window.requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')))}
function applyUIScale(v,snd){S.uiScale=normalizeUIScale(v);ls('ui-scale',String(S.uiScale));if(snd)playClick();updateUIScaleUI();window.dispatchEvent(new Event('resize'))}
function normalizeAccent(v){return['blue','red','green','yellow','pink','purple','orange'].includes(v)?v:'blue'}
function applyAccent(v,snd){S.accent=normalizeAccent(v);ls('accent',S.accent);if(snd)playClick();document.body.dataset.accent=S.accent;$$('[data-accent-value]').forEach(b=>b.classList.toggle('active',b.dataset.accentValue===S.accent));updateThemedLogos();updateWallpaperPreviews()}
// ── Style d'interface (default / Lumen Mirror) ─────────────────────
function normalizeUiStyle(v){return v==='glass'?'glass':'default'}
function applyGlassTransparencyVar(){
  // Mappe 0..100 sur des plages cohérentes pour --glass-alpha, --glass-blur,
  // --glass-border-a. 0 = quasi opaque/compact, 100 = verre très transparent.
  const n=Math.max(0,Math.min(100,parseInt(S.glassTransparency,10)||0));
  const t=n/100;
  // alpha : 0 → 0.94 (surface pleine, compacte), 100 → 0.05 (très transparent).
  // Courbe ease-out (1-(1-t)^2) : la transparence se creuse vite au début du
  // curseur puis s'affine, ce qui rend toute la course perceptible.
  const ease=1-Math.pow(1-t,2);
  const alpha=(0.94-(0.89*ease)).toFixed(3);
  // blur : 0 → 4px (fond opaque, flou inutile), 100 → 28px (verre profond)
  const blur=(4+(24*t)).toFixed(1)+'px';
  // border : 0 → 0.42 (cadre net), 100 → 0.10 (liseré discret)
  const border=(0.42-(0.32*t)).toFixed(3);
  document.documentElement.style.setProperty('--glass-alpha',alpha);
  document.documentElement.style.setProperty('--glass-blur',blur);
  document.documentElement.style.setProperty('--glass-border-a',border);
}
function applyUiStyle(v,snd){
  S.uiStyle=normalizeUiStyle(v);
  ls('ui-style',S.uiStyle);
  if(snd)playClick();
  document.body.dataset.uiStyle=S.uiStyle;
  $$('[data-ui-style-value]').forEach(b=>b.classList.toggle('active',b.dataset.uiStyleValue===S.uiStyle));
  applyGlassTransparencyVar();
}
function applyGlassTransparency(v,snd){
  const n=Math.max(0,Math.min(100,parseInt(v,10)||0));
  S.glassTransparency=n;
  ls('glass-transparency',String(n));
  if(snd)playClick();
  const input=$('glass-transparency-input');
  const valueEl=$('glass-transparency-value');
  if(input&&input.value!==String(n))input.value=String(n);
  if(valueEl)valueEl.textContent=n+'%';
  applyGlassTransparencyVar();
}
function applyGlassTint(v,snd){
  S.glassTint=v==='on'?'on':'off';
  ls('glass-tint',S.glassTint);
  if(snd)playClick();
  document.body.dataset.glassTint=S.glassTint;
  const tog=$('glass-tint-toggle');
  if(tog)tog.checked=S.glassTint==='on';
}
function applyPixelButtons(v,snd){
  S.pixelButtons=v==='off'?'off':'on';
  ls('pixel-buttons',S.pixelButtons);
  if(snd)playClick();
  document.body.dataset.pixelButtons=S.pixelButtons;
  const tog=$('pixel-buttons-toggle');
  if(tog)tog.checked=S.pixelButtons==='on';
}
function applyAiTyping(v,snd){
  S.aiTyping=v==='off'?'off':'on';
  ls('ai-typing',S.aiTyping);
  if(snd)playClick();
  document.body.dataset.aiTyping=S.aiTyping;
  const tog=$('ai-typing-toggle');
  if(tog)tog.checked=S.aiTyping==='on';
  // Le choix du style d'écriture n'a de sens que si l'effet est activé.
  const styleRow=$('typing-style-row');
  if(styleRow)styleRow.hidden=S.aiTyping!=='on';
}
// ── Style de l'effet d'écriture : "default" (caractère par caractère)
//    ou "discovery" (les mots se révèlent progressivement en fondu) ──
function applyTypingStyle(v,snd){
  S.aiTypingStyle=v==='discovery'?'discovery':'default';
  ls('ai-typing-style',S.aiTypingStyle);
  if(snd)playClick();
  $$('[data-typing-style-value]').forEach(b=>b.classList.toggle('active',b.dataset.typingStyleValue===S.aiTypingStyle));
}
// ── Effets d'envoi (pop de bulle + onde du bouton Envoyer en Lumen Mirror) ──
function applySendEffects(v,snd){
  S.sendEffects=v==='off'?'off':'on';
  ls('send-effects',S.sendEffects);
  if(snd)playClick();
  document.body.dataset.sendEffects=S.sendEffects;
  const tog=$('send-effects-toggle');
  if(tog)tog.checked=S.sendEffects==='on';
}
// ── Lumen Reflex Boost — mode performance maximale ─────
// Coupe TOUTES les animations, transitions, flous et effets décoratifs
// (envoi, écriture caractère par caractère, sonar micro…) pour obtenir
// l'interface la plus fluide possible. Les fonds d'écran sont conservés.
// Réversible : ce mode neutralise les autres effets sans modifier leurs
// réglages — il suffit de le désactiver pour tout retrouver à l'identique.
function boostOn(){return S.reflexBoost==='on'}
function applyReflexBoost(v,snd){
  S.reflexBoost=v==='on'?'on':'off';
  ls('reflex-boost',S.reflexBoost);
  if(snd)playClick();
  document.body.dataset.reflexBoost=S.reflexBoost;
  const tog=$('reflex-boost-toggle');
  if(tog)tog.checked=S.reflexBoost==='on';
}
// ── Effets d'interaction Lumen Mirror ───────────────────────────────
// Onde transitoire au centre d'un bouton (survit au masquage du bouton :
// l'élément est attaché à <body>, utile pour Envoyer qui disparaît aussitôt).
function spawnGlassPressFx(el,kind){
  if(S.uiStyle!=='glass'||S.effects==='off'||boostOn()||!el)return;
  const r=el.getBoundingClientRect();
  if(!r.width&&!r.height)return;
  const fx=document.createElement('div');
  fx.className='glass-press-fx '+kind;
  fx.style.left=(r.left+r.width/2)+'px';
  fx.style.top=(r.top+r.height/2)+'px';
  document.body.appendChild(fx);
  fx.addEventListener('animationend',()=>fx.remove(),{once:true});
  setTimeout(()=>{if(fx.parentNode)fx.remove()},1200);
}
// Pop élastique de la dernière bulle utilisateur après un envoi.
function markLastUserBubbleSent(){
  if(S.uiStyle!=='glass'||S.sendEffects!=='on'||S.effects==='off'||boostOn())return;
  const bubbles=msgBox.querySelectorAll('.message-row.user .bubble');
  const last=bubbles.length?bubbles[bubbles.length-1]:null;
  if(last)last.classList.add('glass-sent');
}
// Effet d'écriture caractère par caractère sur le dernier message assistant.
// Non bloquant : si une autre génération démarre, l'effet en cours s'arrête
// naturellement au prochain renderMessages().
let _typingTokenSeq=0;
function runAiTypingEffect(){
  if(S.aiTyping!=='on'||boostOn())return;
  if(!messages||!messages.length)return;
  const lastIdx=messages.length-1;
  const last=messages[lastIdx];
  if(!last||last[0]==='Vous'||last[1]==='…')return;
  const fullText=String(last[1]||'');
  if(!fullText)return;
  const row=msgBox.querySelectorAll('.message-row.assistant');
  const bubbleHost=row.length?row[row.length-1]:null;
  const bubble=bubbleHost?bubbleHost.querySelector('.bubble'):null;
  if(!bubble)return;
  // Sauvegarde le contenu actuel (le HTML peut contenir des éléments enfants,
  // mais le rendu utilise simplement la chaîne échappée). On garde une copie
  // pour restaurer en cas d'annulation.
  const originalHTML=bubble.innerHTML;
  const token=++_typingTokenSeq;
  // ── Style "Découverte" : les mots se révèlent en fondu, petit à petit. ──
  // Tout le texte est injecté immédiatement (spans), le CSS gère la cadence :
  // non bloquant et annulé naturellement au prochain renderMessages().
  if(S.aiTypingStyle==='discovery'){
    const words=fullText.split(/(\s+)/);
    let wordIdx=0;
    bubble.innerHTML=words.map(w=>{
      if(!w.trim())return esc(w);
      const delayMs=Math.min(wordIdx++*55,6000);
      return '<span class="discover-word" style="animation-delay:'+delayMs+'ms">'+esc(w)+'</span>';
    }).join('');
    const total=Math.min(wordIdx*55,6000)+600;
    setTimeout(()=>{if(token===_typingTokenSeq)bubble.innerHTML=originalHTML},total);
    return;
  }
  // ── Style "Par défaut" : caractère par caractère. ──
  bubble.textContent='';
  // Vitesse : ~16ms par caractère (≈60 chars/s) — fluide sans bloquer la lecture.
  // On groupe par 2 caractères pour rester rapide sur les longs textes.
  const step=Math.max(1,Math.ceil(fullText.length/600));
  const delay=16;
  let i=0;
  function tick(){
    if(token!==_typingTokenSeq){bubble.innerHTML=originalHTML;return}
    i=Math.min(fullText.length,i+step);
    bubble.textContent=fullText.slice(0,i);
    if(i<fullText.length){setTimeout(tick,delay)}
    else{bubble.innerHTML=originalHTML}
  }
  tick();
}
function normalizeWallpaperVolume(v){const n=parseInt(v,10);return Number.isFinite(n)?Math.max(0,Math.min(100,n)):35}
function wallpaperStateFor(target){return target==='coworking'?{type:S.wallpaperCoworkingType,src:S.wallpaperCoworkingSrc,volume:normalizeWallpaperVolume(S.wallpaperCoworkingVolume)}:{type:S.wallpaperNormalType,src:S.wallpaperNormalSrc,volume:normalizeWallpaperVolume(S.wallpaperNormalVolume)}}
function setWallpaperVolume(target,volume){const safeVolume=normalizeWallpaperVolume(volume);if(target==='coworking'){S.wallpaperCoworkingVolume=safeVolume;ls('wallpaper-coworking-volume',String(safeVolume))}else{S.wallpaperNormalVolume=safeVolume;ls('wallpaper-normal-volume',String(safeVolume))}if(activeTab===target){wallpaperVideo.volume=safeVolume/100;wallpaperVideo.muted=safeVolume<=0}if(wallpaperVolumeValue)wallpaperVolumeValue.textContent=safeVolume+'%'}
function setWallpaperState(target,type,src){const safeType=(type==='image'||type==='video')?type:'none';const safeSrc=src||'';if(target==='coworking'){S.wallpaperCoworkingType=safeType;S.wallpaperCoworkingSrc=safeSrc;ls('wallpaper-coworking-type',safeType);ls('wallpaper-coworking-src',safeSrc)}else{S.wallpaperNormalType=safeType;S.wallpaperNormalSrc=safeSrc;ls('wallpaper-normal-type',safeType);ls('wallpaper-normal-src',safeSrc)}applyWallpaper();updateWallpaperPreviews()}
function tryPlayWallpaperVideo(){if(!wallpaperVideo||!wallpaperVideo.classList.contains('show'))return;const p=wallpaperVideo.play();if(p&&typeof p.catch==='function')p.catch(()=>{})}
function applyWallpaper(){const activeTarget=activeTab==='coworking'?'coworking':'normal';const data=wallpaperStateFor(activeTarget);const has=data.type!=='none'&&!!data.src;document.body.dataset.wallpaperActive=has?'on':'off';document.body.dataset.cwWallpaper=(S.wallpaperCoworkingType!=='none'&&S.wallpaperCoworkingSrc)?'on':'off';wallpaperImage.classList.remove('show');wallpaperVideo.classList.remove('show');wallpaperImage.removeAttribute('src');wallpaperVideo.pause();wallpaperVideo.removeAttribute('src');wallpaperVideo.load();if(!has)return;if(data.type==='image'){wallpaperImage.src=data.src;wallpaperImage.classList.add('show');return}wallpaperVideo.preload='auto';wallpaperVideo.src=data.src;wallpaperVideo.classList.add('show');wallpaperVideo.loop=true;wallpaperVideo.playsInline=true;wallpaperVideo.volume=data.volume/100;wallpaperVideo.muted=data.volume<=0;const maxW=S.videoQuality==='4k'?3840:1920;wallpaperVideo.style.maxWidth=maxW+'px';wallpaperVideo.style.maxHeight=(maxW===3840?2160:1080)+'px';tryPlayWallpaperVideo()}
function renderWallpaperPreviewBox(box,data){if(!box)return;const label=box.querySelector('.label');box.innerHTML='';if(data.type==='image'&&data.src){const img=document.createElement('img');img.src=data.src;img.alt='';box.appendChild(img)}else if(data.type==='video'&&data.src){const vid=document.createElement('video');vid.src=data.src;vid.muted=true;vid.loop=true;vid.autoplay=true;vid.playsInline=true;vid.addEventListener('canplay',()=>{vid.play().catch(()=>{})},{once:true});box.appendChild(vid)}if(label)box.appendChild(label);else{const span=document.createElement('span');span.className='label';span.textContent=t('appearance_preview');box.appendChild(span)}}
function updateWallpaperPreviews(){renderWallpaperPreviewBox(normalWallpaperPreview,wallpaperStateFor('normal'));renderWallpaperPreviewBox(coworkingWallpaperPreview,wallpaperStateFor('coworking'));renderWallpaperPreviewBox(wallpaperModalPreview,wallpaperStateFor(wallpaperTarget))}
function openWallpaperModal(target){wallpaperTarget=target==='coworking'?'coworking':'normal';wallpaperModalTitle.textContent=t('appearance_modal_title');wallpaperModalTarget.textContent=wallpaperTarget==='coworking'?t('appearance_wallpaper_coworking'):t('appearance_wallpaper_normal');const state=wallpaperStateFor(wallpaperTarget);if(wallpaperVolumeInput)wallpaperVolumeInput.value=String(state.volume);if(wallpaperVolumeValue)wallpaperVolumeValue.textContent=state.volume+'%';updateWallpaperPreviews();wallpaperBackdrop.classList.add('open')}
function closeWallpaperModal(){wallpaperBackdrop.classList.remove('open');wallpaperFileInput.value='';wallpaperVideoFileInput.value=''}
async function handleWallpaperImage(file){if(!file||!file.type.startsWith('image/'))return;try{const dataUrl=await readFileAsDataURL(file);const moderation=await apiModerateProfileImage(file.name||'wallpaper',dataUrl);if(!moderation.safe){alert(moderation.reason||"Cette image ne respecte pas nos règles d'utilisation.");return}setWallpaperState(wallpaperTarget,'image',dataUrl);updateWallpaperPreviews()}catch(err){alert("Impossible de vérifier l'image. Veuillez réessayer.")}}
async function handleWallpaperVideo(file){if(!file||!file.type.startsWith('video/'))return;const reader=new FileReader();reader.onload=()=>{setWallpaperState(wallpaperTarget,'video',String(reader.result||''));setWallpaperVolume(wallpaperTarget,wallpaperVolumeInput?wallpaperVolumeInput.value:35);updateWallpaperPreviews();tryPlayWallpaperVideo()};reader.readAsDataURL(file)}

function applyOptResp(v,snd){apply('optResp',v==='on'?'on':'off','optresp',snd);enforceMode();renderModes();updateModeUI();updatePerf()}
function applyCalcTarget(v,snd,showNotif){const next=['cpu','gpu','default'].includes(v)?v:defs.calcTarget;apply('calcTarget',next,'calc-target',snd);updateCalcTargetUI();if(showNotif){const key='calc_target_notify_'+next;calcTargetNotification.textContent=t(key);calcTargetNotification.hidden=false;setTimeout(()=>{calcTargetNotification.hidden=true},6000)}}
const calcTargetOptions=[{id:'cpu',icon:'🖥️',labelKey:'calc_target_cpu'},{id:'gpu',icon:'🎮',labelKey:'calc_target_gpu'},{id:'default',icon:'⚡',labelKey:'calc_target_default'}];
function updateCalcTargetUI(){const current=calcTargetOptions.find(o=>o.id===S.calcTarget)||calcTargetOptions[2];calcTargetLabel.textContent=t(current.labelKey);calcTargetIcon.textContent=current.icon;renderCalcTargetMenu()}
function renderCalcTargetMenu(){calcTargetMenu.innerHTML=calcTargetOptions.map(o=>'<button type="button" class="dropdown-menu-item'+(o.id===S.calcTarget?' selected':'')+'" data-ct-value="'+esc(o.id)+'" role="menuitemradio"><span class="dm-icon">'+o.icon+'</span><span class="dm-label">'+esc(t(o.labelKey))+'</span><span class="dm-check">✓</span></button>').join('')}
// Portail vers document.body : .settings-modal est en transform → position:fixed
// est interprétée par rapport à la modale (et clippée par overflow:hidden).
// On déplace donc temporairement le menu sous <body> pour qu'il s'ancre au viewport.
let _calcTargetParent=null,_calcTargetNext=null;
function openCalcTargetMenu(){
  if(!calcTargetMenu)return;
  if(calcTargetMenu.parentNode!==document.body){
    _calcTargetParent=calcTargetMenu.parentNode;
    _calcTargetNext=calcTargetMenu.nextSibling;
    document.body.appendChild(calcTargetMenu);
  }
  const rect=calcTargetTrigger.getBoundingClientRect();
  const menuW=Math.max(280,rect.width);
  const left=Math.min(window.innerWidth-menuW-12,Math.max(12,rect.left));
  // Si pas assez de place sous le bouton, on bascule au-dessus.
  const spaceBelow=window.innerHeight-rect.bottom;
  const above=spaceBelow<260&&rect.top>260;
  calcTargetMenu.style.top=(above?(rect.top-8-Math.min(260,calcTargetMenu.scrollHeight||260)):(rect.bottom+8))+'px';
  calcTargetMenu.style.left=left+'px';
  calcTargetMenu.style.minWidth=menuW+'px';
  calcTargetMenu.classList.add('open');
  calcTargetTrigger.setAttribute('aria-expanded','true');
}
function closeCalcTargetMenu(){
  if(!calcTargetMenu)return;
  calcTargetMenu.classList.remove('open');
  calcTargetTrigger.setAttribute('aria-expanded','false');
  // Restaure la position DOM d'origine (utile si l'on rouvre la modale Settings).
  if(_calcTargetParent&&calcTargetMenu.parentNode===document.body){
    _calcTargetParent.insertBefore(calcTargetMenu,_calcTargetNext||null);
    _calcTargetParent=null;_calcTargetNext=null;
  }
}
// Ferme le menu si l'on clique à l'extérieur (le menu étant maintenant détaché).
document.addEventListener('click',e=>{
  if(!calcTargetMenu||!calcTargetMenu.classList.contains('open'))return;
  if(calcTargetMenu.contains(e.target)||(calcTargetTrigger&&calcTargetTrigger.contains(e.target)))return;
  closeCalcTargetMenu();
});
// Repositionne en cas de scroll/resize tant qu'il est ouvert.
window.addEventListener('resize',()=>{if(calcTargetMenu&&calcTargetMenu.classList.contains('open'))openCalcTargetMenu()});
window.addEventListener('scroll',()=>{if(calcTargetMenu&&calcTargetMenu.classList.contains('open'))openCalcTargetMenu()},true);
function applyUiOpt(v,snd){apply('uiOpt',v==='on'?'on':'off','uiopt',snd);if(S.uiOpt==='on'){applyEffects('off',false);applyKbSound('off',false);applyClickSound('off',false);applyAiSound('off',false)}updatePerf()}
function applyKbSound(v,snd){apply('kbSound',v==='on'?'on':'off','kb-sound',snd);$$('[data-kb-sound]').forEach(b=>b.classList.toggle('active',b.dataset.kbSound===S.kbSound));updateSndVis();if(v==='on')checkUiOptOff()}
function applyKbStyle(v,snd){apply('kbStyle',['bulle','aurela','verdrock','feryn'].includes(v)?v:'bulle','kb-style',snd);$$('[data-kb-style]').forEach(b=>b.classList.toggle('active',b.dataset.kbStyle===S.kbStyle))}
function applyClickSound(v,snd){apply('clickSound',v==='on'?'on':'off','click-sound',snd);$$('[data-click-sound]').forEach(b=>b.classList.toggle('active',b.dataset.clickSound===S.clickSound));updateSndVis();if(v==='on')checkUiOptOff()}
function applyClickStyle(v,snd){apply('clickStyle',['bulle','nebrise'].includes(v)?v:'bulle','click-style',snd);$$('[data-click-style]').forEach(b=>b.classList.toggle('active',b.dataset.clickStyle===S.clickStyle))}
function applyAiSound(v,snd){apply('aiSound',v==='on'?'on':'off','ai-sound',snd);$$('[data-ai-sound]').forEach(b=>b.classList.toggle('active',b.dataset.aiSound===S.aiSound));if(v==='on')checkUiOptOff()}
function updateSndVis(){const kr=$('keyboard-style-row'),cr=$('click-style-row');if(kr)kr.hidden=S.kbSound!=='on';if(cr)cr.hidden=S.clickSound!=='on'}
function updatePerf(){$('effects-state').textContent=S.effects==='off'?t('state_on'):t('state_off');$('responses-state').textContent=S.optResp==='on'?t('state_on'):t('state_off');const uiOptState=$('uiopt-state');if(uiOptState)uiOptState.textContent=S.uiOpt==='on'?t('state_on'):t('state_off');updateCalcTargetUI()}
function getCoworkingContent(){return coworkingContent[S.lang]||coworkingContent[defs.lang]||coworkingContent.fr}
function pickRandom(arr){return arr[Math.floor(Math.random()*arr.length)]}
function refreshWelcomeContent(){
  if(messages.length)return;
  if(S.privateChat){
    welcomeEl.textContent=t('private_chat_welcome');
    welcomeDesc.textContent=t('private_chat_welcome_desc');
    return;
  }
  if(activeTab==='coworking'){
    const cfg=getCoworkingContent();
    welcomeEl.textContent=pickRandom(cfg.messages);
    welcomeDesc.textContent=cfg.desc||'';
    return;
  }
  const pool=WP[S.lang]||WP[defs.lang]||['...'];
  welcomeEl.textContent=pickRandom(pool);
  welcomeDesc.textContent='';
}
function updateTabUI(){
  document.body.dataset.activeTab=activeTab;
  if(tabChat)tabChat.classList.toggle('active',activeTab==='chat');
  if(tabCoworking)tabCoworking.classList.toggle('active',activeTab==='coworking');
  if(modePanel)modePanel.hidden=activeTab==='coworking';
  if(modeAnn)modeAnn.hidden=activeTab==='coworking';
  ta.placeholder=activeTab==='coworking'?getCoworkingContent().placeholder:t('placeholder');
  statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);
  applyWallpaper();
  updateThemedLogos();
  refreshWelcomeContent();
}
async function switchTabWithReset(targetTab){
  if(activeTab===targetTab)return;
  statusEl.textContent='...';
  try{const p=await apiNewChat();messages=p.messages;messagesMeta=p.metas||[];openSpecificityPanels.clear()}catch(e){statusEl.textContent=e.message;return}
  activeTab=targetTab==='coworking'?'coworking':'chat';
  closeModelDD();closeMM();closeSM();
  refreshWelcomeContent();updateTabUI();renderMessages();ta.value='';autoResize();statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);
}
function setActiveTab(tab,refresh){
  activeTab=tab==='coworking'?'coworking':'chat';
  closeModelDD();
  closeMM();
  closeSM();
  if(refresh!==false)refreshWelcomeContent();
  updateTabUI();
}
function applyTranslations(){$$('[data-i18n]').forEach(n=>n.textContent=t(n.dataset.i18n));$$('[data-placeholder-key]').forEach(n=>n.placeholder=t(n.dataset.placeholderKey));$('settings-button-label').textContent=t('settings_label');$('newchat-button-label').textContent=t('new_chat');const _sl=$('sidebar-new-chat-label');if(_sl)_sl.textContent=t('new_chat');updateSidebarProfile();$('settings-version-value').textContent=appVersion;brandText.textContent=appTitle();plusAddSheet.textContent='📄 '+t('add_sheet');const mcb=$('migrate-copy-btn');if(mcb)mcb.textContent=t('migrate_copy');updatePrivateChatLabels();updateCharCounter();updateContraction();updatePerf();updateUIScaleUI();updateModeUI();renderModes();updateStyleUI();renderStyles();updateGadgetUI();renderGadgets();renderModelDD();if(typeof renderCustomModelsMenu==='function')renderCustomModelsMenu();if(typeof updateCustomModelTriggerUI==='function')updateCustomModelTriggerUI();updateTabUI();updateProfileUI();updateWallpaperPreviews();toggleProfileEditor(!profileEditor.hidden);renderMessages()}
function persistPerso(){ls('firstname',$('user-firstname').value);ls('lastname',$('user-lastname').value);ls('tone',$('user-tone').value);ls('info',$('user-info').value);updateSidebarProfile()}
function loadPerso(){$('user-firstname').value=ls('firstname')||'';$('user-lastname').value=ls('lastname')||'';$('user-tone').value=ls('tone')||'';$('user-info').value=ls('info')||''}
function profileGet(key,def=''){const v=ls('profile-'+key);return v===null||v===undefined||v===''?def:v}
function profileSet(key,val){ls('profile-'+key,val||'');return val||''}
function getChatCount(){const raw=ls('stats-chat-count');if(raw===null){const seeded=messages.filter(m=>Array.isArray(m)&&m[0]==='Vous').length;ls('stats-chat-count',String(seeded));return seeded}const n=parseInt(raw,10);return Number.isFinite(n)&&n>=0?n:0}
function setChatCount(n){ls('stats-chat-count',String(Math.max(0,Math.floor(n))));updateProfileUI()}
function incrementChatCount(){setChatCount(getChatCount()+1)}
function computeGoatScore(count){return Math.floor((count*10)+(Math.sqrt(Math.max(0,count))*25))}
function getProfileData(){return{firstname:profileGet('firstname'),lastname:profileGet('lastname'),bio:profileGet('bio'),avatar:profileGet('avatar'),banner:profileGet('banner'),instagram:profileGet('instagram'),tiktok:profileGet('tiktok'),youtube:profileGet('youtube'),github:profileGet('github'),bluesky:profileGet('bluesky'),showMessageAvatar:profileGet('showMessageAvatar','off')}}
function getProfileFullName(data){const full=[data.firstname,data.lastname].filter(Boolean).join(' ').trim();return full||t('profile_no_name')}
function normalizeSocialUrl(platform,value){const raw=String(value||'').trim();if(!raw)return'';if(/^https?:\/\//i.test(raw))return raw;const clean=raw.replace(/^@+/,'');const bases={instagram:'https://www.instagram.com/',tiktok:'https://www.tiktok.com/@',youtube:'https://www.youtube.com/@',github:'https://github.com/',bluesky:'https://bsky.app/profile/'};return(bases[platform]||'https://')+clean}
function socialEntries(data){return[]}
function svgDataUri(svg){return 'data:image/svg+xml;charset=UTF-8,'+encodeURIComponent(svg)}
function makeGoatAvatarPreset(id,title,c1,c2,accent){return{id,label:title,src:svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="${id}-bg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="${c1}"/><stop offset="100%" stop-color="${c2}"/></linearGradient></defs><rect width="512" height="512" rx="120" fill="url(#${id}-bg)"/><circle cx="256" cy="208" r="124" fill="rgba(255,255,255,.15)"/><path d="M168 352c28-36 59-54 88-54s60 18 88 54" fill="none" stroke="rgba(255,255,255,.92)" stroke-width="28" stroke-linecap="round"/><text x="256" y="246" text-anchor="middle" font-family="JetBrains Mono, Arial" font-size="132" font-weight="800" fill="${accent}">G</text><text x="256" y="424" text-anchor="middle" font-family="JetBrains Mono, Arial" font-size="52" font-weight="700" fill="rgba(255,255,255,.92)">GOAT</text><!-- goat-preset --></svg>`)} }
function makeGoatBannerPreset(id,title,c1,c2,accent){return{id,label:title,src:svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 500"><defs><linearGradient id="${id}-bg" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="${c1}"/><stop offset="100%" stop-color="${c2}"/></linearGradient></defs><rect width="1600" height="500" rx="42" fill="url(#${id}-bg)"/><circle cx="1250" cy="120" r="190" fill="rgba(255,255,255,.08)"/><circle cx="1340" cy="340" r="220" fill="rgba(255,255,255,.06)"/><path d="M0 360c170-50 280-66 430-36s260 56 410 10 320-84 760 24v142H0z" fill="rgba(10,15,35,.18)"/><text x="120" y="188" font-family="JetBrains Mono, Arial" font-size="150" font-weight="800" fill="${accent}">LE GOAT</text><text x="124" y="260" font-family="JetBrains Mono, Arial" font-size="46" font-weight="600" fill="rgba(255,255,255,.88)">Designed and coded in France</text><path d="M1048 214c40-40 74-60 102-60 30 0 60 20 100 60" fill="none" stroke="rgba(255,255,255,.92)" stroke-width="22" stroke-linecap="round"/><circle cx="1084" cy="170" r="18" fill="rgba(255,255,255,.92)"/><circle cx="1164" cy="170" r="18" fill="rgba(255,255,255,.92)"/><!-- goat-banner-preset --></svg>`)} }
let profilePresetLibrary=null;
function getProfilePresetLibrary(){
  if(profilePresetLibrary)return profilePresetLibrary;
  const logo=$('main-logo')?$('main-logo').getAttribute('src'):'';
  // Utilise les images locales si disponibles, sinon fallback sur les presets SVG
  const localAvatars=(localProfilePresets&&localProfilePresets.avatars)||[];
  const localBanners=(localProfilePresets&&localProfilePresets.banners)||[];
  const fallbackAvatars=[
    logo?{id:'goat-logo',label:'Logo Le Goat',src:logo}:makeGoatAvatarPreset('goat-logo','Logo Le Goat','#f8fafc','#e5e7eb','#111827'),
    makeGoatAvatarPreset('goat-midnight','Goat Midnight','#0f172a','#2563eb','#ffffff'),
    makeGoatAvatarPreset('goat-ultra','Goat Ultra','#0b1020','#7c3aed','#e0f2fe'),
    makeGoatAvatarPreset('goat-frost','Goat Frost','#eff6ff','#93c5fd','#1d4ed8')
  ];
  const fallbackBanners=[
    makeGoatBannerPreset('goat-banner-core','Goat Core','#111827','#2563eb','#ffffff'),
    makeGoatBannerPreset('goat-banner-neon','Goat Neon','#0f172a','#7c3aed','#f8fafc'),
    makeGoatBannerPreset('goat-banner-light','Goat Horizon','#1e3a8a','#60a5fa','#ffffff')
  ];
  profilePresetLibrary={
    avatar: localAvatars.length>0 ? localAvatars : fallbackAvatars,
    banner: localBanners.length>0 ? localBanners : fallbackBanners
  };
  return profilePresetLibrary;
}
function isLogoStyleAvatarSrc(src){const logo=$('main-logo')?$('main-logo').getAttribute('src'):'';return!!src&&(src===logo||src.indexOf('goat-preset')!==-1)}
function applyAvatarFitMode(el,src){if(!el)return;el.classList.toggle('is-logo',isLogoStyleAvatarSrc(src))}
function setUploadPreview(box,src,fallbackLabel,kind){if(!box)return;box.innerHTML=src?'<img class="'+((kind==='avatar'&&isLogoStyleAvatarSrc(src))?'is-logo':'')+'" src="'+esc(src)+'" alt="preview">':'<span>'+esc(fallbackLabel)+'</span>'}
function toggleProfileEditor(force){const open=typeof force==='boolean'?force:profileEditor.hidden;profileEditor.hidden=!open;profileEditToggle.textContent=open?t('profile_close_edit'):t('profile_edit')}
function loadProfileForm(){const data=getProfileData();profileFirstnameInput.value=data.firstname;profileLastnameInput.value=data.lastname;profileBioInput.value=data.bio;profileInstagramInput.value=data.instagram;profileTikTokInput.value=data.tiktok;profileYouTubeInput.value=data.youtube;profileGitHubInput.value=data.github;profileBlueskyInput.value=data.bluesky;if(profileAvatarMessagesToggle)profileAvatarMessagesToggle.checked=data.showMessageAvatar==='on';setUploadPreview(profileAvatarUploadPreview,data.avatar,t('profile_avatar'),'avatar');setUploadPreview(profileBannerUploadPreview,data.banner,t('profile_banner'),'banner');updateProfileUI()}
function persistProfileForm(){profileSet('firstname',profileFirstnameInput.value.trim());profileSet('lastname',profileLastnameInput.value.trim());profileSet('bio',profileBioInput.value.trim());profileSet('instagram',profileInstagramInput.value.trim());profileSet('tiktok',profileTikTokInput.value.trim());profileSet('youtube',profileYouTubeInput.value.trim());profileSet('github',profileGitHubInput.value.trim());profileSet('bluesky',profileBlueskyInput.value.trim());updateProfileUI()}
function updateProfileUI(){if(!profileNamePreview)return;const data=getProfileData();const count=getChatCount();const score=computeGoatScore(count);const fullName=getProfileFullName(data);const fallbackAvatar=$('main-logo')?$('main-logo').getAttribute('src'):'';const avatarSrc=data.avatar||fallbackAvatar;profileNamePreview.textContent=fullName;profileDescriptionPreview.textContent=data.bio||t('profile_no_description');profileDescriptionPreview.classList.toggle('empty',!data.bio);if(profileChatCount)profileChatCount.textContent=count.toLocaleString('fr-FR');if(profileGoatScore)profileGoatScore.textContent=score.toLocaleString('fr-FR');profileAvatarPreview.src=avatarSrc;applyAvatarFitMode(profileAvatarPreview,avatarSrc);profileBannerPreview.style.backgroundImage=data.banner?'url("'+String(data.banner).replace(/"/g,'\"')+'")':'';if(settingsProfileTabAvatar){settingsProfileTabAvatar.src=avatarSrc;applyAvatarFitMode(settingsProfileTabAvatar,avatarSrc)}if(settingsProfileTabName)settingsProfileTabName.textContent=fullName;setUploadPreview(profileAvatarUploadPreview,data.avatar,t('profile_avatar'),'avatar');setUploadPreview(profileBannerUploadPreview,data.banner,t('profile_banner'),'banner');if(profileAvatarMessagesToggle)profileAvatarMessagesToggle.checked=data.showMessageAvatar==='on';const socials=socialEntries(data).filter(item=>item.value.trim());if(!socials.length){profileSocialsPreview.innerHTML='<span class="profile-social-empty">'+esc(t('profile_share_hint'))+'</span>'}else{profileSocialsPreview.innerHTML=socials.map(item=>'<a class="profile-social-link" href="'+esc(normalizeSocialUrl(item.id,item.value))+'" target="_blank" rel="noreferrer noopener">'+esc(item.label)+'</a>').join('')}updateSidebarProfile();}
function closeProfilePicker(){if(!profilePickerBackdrop)return;profilePickerBackdrop.classList.remove('open')}
function renderProfilePicker(){if(!profilePickerGrid)return;const library=getProfilePresetLibrary()[profilePickerMode]||[];if(profilePickerTitle)profilePickerTitle.textContent=profilePickerMode==='banner'?t('profile_picker_title_banner'):t('profile_picker_title');if(profilePickerSectionTitle)profilePickerSectionTitle.textContent=t('profile_picker_category_goat');profilePickerGrid.innerHTML='';profilePickerGrid.classList.toggle('banner-mode',profilePickerMode==='banner');library.forEach(item=>{const btn=document.createElement('button');btn.type='button';btn.className='profile-picker-card';const thumb=document.createElement('div');thumb.className='profile-picker-thumb'+(profilePickerMode==='banner'?' banner':'');const img=document.createElement('img');img.src=item.src;if(profilePickerMode==='avatar')applyAvatarFitMode(img,item.src);thumb.appendChild(img);const label=document.createElement('span');label.className='profile-picker-card-label';label.textContent=item.label;btn.appendChild(thumb);btn.appendChild(label);btn.addEventListener('click',()=>{playClick();profileSet(profilePickerMode,item.src);loadProfileForm();closeProfilePicker();renderMessages()});profilePickerGrid.appendChild(btn)});const importBtn=document.createElement('button');importBtn.type='button';importBtn.className='profile-picker-card import';const importThumb=document.createElement('div');importThumb.className='profile-picker-thumb'+(profilePickerMode==='banner'?' banner':'');importThumb.innerHTML='<div>+</div><span>'+esc(profilePickerMode==='banner'?t('profile_picker_import_banner'):t('profile_picker_import_avatar'))+'</span>';const importLabel=document.createElement('span');importLabel.className='profile-picker-card-label';importLabel.textContent=profilePickerMode==='banner'?t('profile_choose_banner'):t('profile_choose_avatar');importBtn.appendChild(importThumb);importBtn.appendChild(importLabel);importBtn.addEventListener('click',()=>{playClick();closeProfilePicker();(profilePickerMode==='banner'?profileBannerFile:profileAvatarFile).click()});profilePickerGrid.appendChild(importBtn)}
function openProfilePicker(mode){profilePickerMode=mode||'avatar';renderProfilePicker();if(profilePickerBackdrop)profilePickerBackdrop.classList.add('open')}
function readFileAsDataURL(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(reader.error||new Error('read error'));reader.readAsDataURL(file)})}
async function apiModerateProfileImage(filename,dataUrl){const r=await fetch('/api/moderate_profile_image',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename,dataUrl})});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Filtre image indisponible');return p}
function closeCropper(){cropState=null;cropBackdrop.classList.remove('open');cropCanvas.classList.remove('dragging')}
function cropAspect(mode){return mode==='banner'?3.2:1}
function resizeCropCanvas(){if(!cropState)return;const rect=cropCanvas.getBoundingClientRect();const ratio=window.devicePixelRatio||1;cropCanvas.width=Math.max(1,Math.round(rect.width*ratio));cropCanvas.height=Math.max(1,Math.round(rect.height*ratio));cropState.pixelRatio=ratio;cropState.canvasW=rect.width;cropState.canvasH=rect.height}
function initCropState(){if(!cropState||!cropState.img)return;resizeCropCanvas();const aspect=cropAspect(cropState.mode);let frameW=Math.min(cropState.canvasW*(cropState.mode==='banner'?0.82:0.58),cropState.canvasW-48);let frameH=frameW/aspect;if(frameH>cropState.canvasH*0.76){frameH=cropState.canvasH*0.76;frameW=frameH*aspect}cropState.frame={x:(cropState.canvasW-frameW)/2,y:(cropState.canvasH-frameH)/2,w:frameW,h:frameH};cropState.baseScale=Math.max(frameW/cropState.img.width,frameH/cropState.img.height);cropState.zoom=1;cropState.offsetX=0;cropState.offsetY=0;if(cropZoom)cropZoom.value='100';clampCropOffsets();renderCropper()}
function clampCropOffsets(){if(!cropState||!cropState.frame)return;const drawW=cropState.img.width*cropState.baseScale*cropState.zoom;const drawH=cropState.img.height*cropState.baseScale*cropState.zoom;const f=cropState.frame;const minOffsetX=f.x+f.w-drawW/2-cropState.canvasW/2;const maxOffsetX=f.x+drawW/2-cropState.canvasW/2;const minOffsetY=f.y+f.h-drawH/2-cropState.canvasH/2;const maxOffsetY=f.y+drawH/2-cropState.canvasH/2;cropState.offsetX=Math.min(maxOffsetX,Math.max(minOffsetX,cropState.offsetX));cropState.offsetY=Math.min(maxOffsetY,Math.max(minOffsetY,cropState.offsetY))}
function renderCropper(){if(!cropState)return;resizeCropCanvas();const ctx=cropCanvas.getContext('2d');const ratio=cropState.pixelRatio||1;ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,cropState.canvasW,cropState.canvasH);const drawW=cropState.img.width*cropState.baseScale*cropState.zoom;const drawH=cropState.img.height*cropState.baseScale*cropState.zoom;const centerX=cropState.canvasW/2+cropState.offsetX;const centerY=cropState.canvasH/2+cropState.offsetY;const dx=centerX-drawW/2;const dy=centerY-drawH/2;cropState.draw={dx,dy,dw:drawW,dh:drawH};ctx.drawImage(cropState.img,dx,dy,drawW,drawH);ctx.fillStyle='rgba(3,8,20,.56)';ctx.fillRect(0,0,cropState.canvasW,cropState.canvasH);const f=cropState.frame;ctx.save();ctx.beginPath();ctx.rect(f.x,f.y,f.w,f.h);ctx.clip();ctx.clearRect(f.x,f.y,f.w,f.h);ctx.drawImage(cropState.img,dx,dy,drawW,drawH);ctx.restore();ctx.strokeStyle='#ffffff';ctx.lineWidth=2;ctx.strokeRect(f.x,f.y,f.w,f.h);ctx.strokeStyle='rgba(255,255,255,.35)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(f.x+f.w/3,f.y);ctx.lineTo(f.x+f.w/3,f.y+f.h);ctx.moveTo(f.x+2*f.w/3,f.y);ctx.lineTo(f.x+2*f.w/3,f.y+f.h);ctx.moveTo(f.x,f.y+f.h/3);ctx.lineTo(f.x+f.w,f.y+f.h/3);ctx.moveTo(f.x,f.y+2*f.h/3);ctx.lineTo(f.x+f.w,f.y+2*f.h/3);ctx.stroke()}
function openCropper(dataUrl,mode){cropState={mode,img:new Image(),zoom:1,offsetX:0,offsetY:0,pointerId:null};cropTitle.textContent=mode==='banner'?'Recadrer la bannière':'Recadrer la photo de profil';cropBackdrop.classList.add('open');cropState.img.onload=()=>initCropState();cropState.img.src=dataUrl}
function applyCrop(){if(!cropState||!cropState.draw)return;const f=cropState.frame;const d=cropState.draw;const scale=cropState.baseScale*cropState.zoom;const sx=Math.max(0,(f.x-d.dx)/scale);const sy=Math.max(0,(f.y-d.dy)/scale);const sw=Math.min(cropState.img.width-sx,f.w/scale);const sh=Math.min(cropState.img.height-sy,f.h/scale);const out=document.createElement('canvas');out.width=cropState.mode==='banner'?1600:768;out.height=cropState.mode==='banner'?500:768;const octx=out.getContext('2d');octx.drawImage(cropState.img,sx,sy,sw,sh,0,0,out.width,out.height);profileSet(cropState.mode,out.toDataURL('image/png'));closeCropper();loadProfileForm();renderMessages()}
async function handleProfileImage(file,key){if(!file)return;try{const dataUrl=await readFileAsDataURL(file);const moderation=await apiModerateProfileImage(file.name||'',dataUrl);if(!moderation.safe){alert(moderation.reason||"Désolé, nous ne pouvons pas mettre votre photo de profil en raison de nos règles d'utilisation.");return}openCropper(dataUrl,key)}catch(err){alert("Impossible de vérifier l'image. Veuillez réessayer.")}}
function formatProfileText(includeScore){const data=getProfileData();const count=getChatCount();const lines=[getProfileFullName(data)];if(data.bio)lines.push(data.bio);lines.push(t('profile_chats_sent')+' : '+count);if(includeScore)lines.push(t('profile_goat_score')+' : '+computeGoatScore(count));socialEntries(data).forEach(item=>{if(item.value.trim())lines.push(item.label+' : '+normalizeSocialUrl(item.id,item.value))});return lines.filter(Boolean).join('\n')}
function sanitizeFilename(value){return String(value||'profil-goat').normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-zA-Z0-9_-]+/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'').toLowerCase()||'profil-goat'}
async function apiExportProfilePdf(includeScore){const payload={includeScore,chatCount:getChatCount(),goatScore:computeGoatScore(getChatCount()),profile:getProfileData()};const r=await fetch('/api/export_profile_pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Export PDF impossible');return p}
async function apiProfileScreenshot(){const r=await fetch('/api/profile_screenshot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Profile screenshot unavailable');return p}
async function shareProfile(includeScore){playClick();if(includeScore){try{const p=await apiProfileScreenshot();if(p.triggered)return}catch(e){}window.open('https://screenrec.com/fr/','_blank','noopener');return}alert(t('profile_share_dev'))}
async function apiVoiceShortcut(){const r=await fetch('/api/voice_shortcut',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Voice shortcut unavailable');return p}
async function triggerVoiceInput(){
  playClick();
  // Effet micro (Lumen Mirror) : sonar + pression physique — distinct de l'envoi.
  spawnGlassPressFx(voiceInputBtn,'mic');
  if(S.uiStyle==='glass'&&S.effects!=='off'&&!boostOn()&&voiceInputBtn){
    voiceInputBtn.classList.remove('glass-mic-press');
    void voiceInputBtn.offsetWidth;
    voiceInputBtn.classList.add('glass-mic-press');
    voiceInputBtn.addEventListener('animationend',()=>voiceInputBtn.classList.remove('glass-mic-press'),{once:true});
  }
  try{const p=await apiVoiceShortcut();if(p.triggered)return}catch(e){}
  window.open('https://wisprflow.ai/','_blank','noopener')
}
// ── API HTTP — communication avec le backend Python ──────────────
// Toutes les requêtes sont en POST JSON vers localhost.
// Les endpoints sont définis dans GoatRequestHandler (Python).
// ── Construction du contexte « Spécificité » envoyé avec chaque requête ──
// On regroupe ici les méta-données affichées dans le panneau dépliant côté
// frontend : mode, style, modèle (standard ou custom), pièces jointes.
function buildRequestContext(){
  const customActive=(typeof cmHasCustomActive==='function')&&cmHasCustomActive();
  const customName=customActive?(cmGet(S.activeCustomModel)||{}).name||'':'';
  return {
    mode: S.mode||'',
    style: S.wstyle||'',
    model: S.model||'',
    customModelName: customName,
    attachments: (attachments||[]).map(a=>({
      name: a.name||'',
      kind: a.kind||'',
      type: a.type||'',
      size: a.size||0,
    })),
  };
}
async function apiSend(msg,signal){const bio=($('profile-bio-input')||{}).value||'';const tone=($('user-tone')||{}).value||'';const ctx=buildRequestContext();const r=await fetch('/api/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({message:msg,userBio:bio,userTone:tone},ctx)),signal});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Erreur');incrementChatCount();return p}
async function apiRegen(signal){const ctx=buildRequestContext();const r=await fetch('/api/regenerate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(ctx),signal});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Erreur');return p}
async function apiNewChat(){const r=await fetch('/api/new_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Erreur');return p}

// ── Soumission du formulaire (envoi message + gestion erreurs) ────
form.addEventListener('submit',async e=>{e.preventDefault();const v=ta.value.trim();if(!v)return;playSend();if(S.sendEffects==='on')spawnGlassPressFx(sendBtn,'send');statusEl.textContent='...';showStopBtn();abortController=new AbortController();messages.push(['Vous',v],[appTitle(),'…']);messagesMeta.push(null,null);renderMessages();markLastUserBubbleSent();ta.value='';autoResize();updateCharCounter();try{const p=await apiSend(v,abortController.signal);messages=p.messages;messagesMeta=p.metas||[];renderMessages();runAiTypingEffect();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(err){if(err.name==='AbortError'){if(messages.length&&messages[messages.length-1][1]==='…'){messages.pop();messagesMeta.pop()}renderMessages()}else{if(messages.length&&messages[messages.length-1][0]!=='Vous')messages[messages.length-1]=[appTitle(),'Erreur : '+err.message];renderMessages();statusEl.textContent=err.message}}finally{hideStopBtn();ta.focus()}});
// ── Liaisons événements contrôles UI ─────────────────────────────
modeTrigger.addEventListener('click',()=>{playClick();modeMenu.classList.contains('open')?closeMM():openMM()});
styleTrigger.addEventListener('click',()=>{playClick();styleMenu.classList.contains('open')?closeSM():openSM()});
/* gadgetTrigger.addEventListener('click',()=>{playClick();gadgetMenu.classList.contains('open')?closeGM():openGM()}); // desactive */
$('settings-button').addEventListener('click',openSettings);$('settings-close').addEventListener('click',closeSettings);backdrop.addEventListener('click',closeSettings);
dragH.addEventListener('mousedown',startDrag);document.addEventListener('mousemove',onDrag);document.addEventListener('mouseup',()=>{dragging=false});
$('newchat-button').addEventListener('click',async()=>{playClick();if(!confirm(t('new_chat_confirm')))return;statusEl.textContent='...';try{const p=await apiNewChat();messages=p.messages;messagesMeta=p.metas||[];openSpecificityPanels.clear();refreshWelcomeContent();renderMessages();statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);ta.value='';autoResize();ta.focus()}catch(e){statusEl.textContent=e.message}});
$$('[data-settings-tab]').forEach(t=>t.addEventListener('click',()=>{playClick();showTab(t.dataset.settingsTab||'general')}));
// Paramètres — tous les boutons data-xxx-value sont liés dynamiquement
$$('[data-language-value]').forEach(b=>b.addEventListener('click',()=>applyLang(b.dataset.languageValue)));
$$('[data-theme-value]').forEach(b=>b.addEventListener('click',()=>applyTheme(b.dataset.themeValue)));
$$('[data-textsize-value]').forEach(b=>b.addEventListener('click',()=>applyTextSize(b.dataset.textsizeValue)));
$$('[data-kb-sound]').forEach(b=>b.addEventListener('click',()=>applyKbSound(b.dataset.kbSound)));
$$('[data-kb-style]').forEach(b=>b.addEventListener('click',()=>applyKbStyle(b.dataset.kbStyle)));
$$('[data-click-sound]').forEach(b=>b.addEventListener('click',()=>applyClickSound(b.dataset.clickSound)));
$$('[data-click-style]').forEach(b=>b.addEventListener('click',()=>applyClickStyle(b.dataset.clickStyle)));
$$('[data-ai-sound]').forEach(b=>b.addEventListener('click',()=>applyAiSound(b.dataset.aiSound)));
$$('[data-aifont-value]').forEach(b=>b.addEventListener('click',()=>applyAiFont(b.dataset.aifontValue)));
$$('[data-userfont-value]').forEach(b=>b.addEventListener('click',()=>applyUserFont(b.dataset.userfontValue)));
$$('[data-accent-value]').forEach(b=>b.addEventListener('click',()=>applyAccent(b.dataset.accentValue,true)));
// ── Liaisons : style d'interface / Lumen Mirror / boutons 8 bits / effet IA ──
$$('[data-ui-style-value]').forEach(b=>b.addEventListener('click',()=>applyUiStyle(b.dataset.uiStyleValue,true)));
(function(){const inp=$('glass-transparency-input');if(inp)inp.addEventListener('input',()=>applyGlassTransparency(inp.value,false))})();
(function(){const tog=$('glass-tint-toggle');if(tog)tog.addEventListener('change',()=>applyGlassTint(tog.checked?'on':'off',true))})();
(function(){const tog=$('pixel-buttons-toggle');if(tog)tog.addEventListener('change',()=>applyPixelButtons(tog.checked?'on':'off',true))})();
(function(){const tog=$('ai-typing-toggle');if(tog)tog.addEventListener('change',()=>applyAiTyping(tog.checked?'on':'off',true))})();
$$('[data-typing-style-value]').forEach(b=>b.addEventListener('click',()=>applyTypingStyle(b.dataset.typingStyleValue,true)));
(function(){const tog=$('send-effects-toggle');if(tog)tog.addEventListener('change',()=>applySendEffects(tog.checked?'on':'off',true))})();
(function(){const tog=$('reflex-boost-toggle');if(tog)tog.addEventListener('change',()=>applyReflexBoost(tog.checked?'on':'off',true))})();
$('change-normal-wallpaper').addEventListener('click',()=>{playClick();openWallpaperModal('normal')});
$('change-coworking-wallpaper').addEventListener('click',()=>{playClick();openWallpaperModal('coworking')});
$('remove-normal-wallpaper').addEventListener('click',()=>{playClick();setWallpaperState('normal','none','')});
$('remove-coworking-wallpaper').addEventListener('click',()=>{playClick();setWallpaperState('coworking','none','')});
wallpaperImportImageBtn.addEventListener('click',()=>{playClick();wallpaperFileInput.click()});
wallpaperImportVideoBtn.addEventListener('click',()=>{playClick();alert(t('appearance_video_import_warning'));wallpaperVideoFileInput.click()});
wallpaperRemoveBtn.addEventListener('click',()=>{playClick();setWallpaperState(wallpaperTarget,'none','');updateWallpaperPreviews()});
wallpaperCloseBtn.addEventListener('click',()=>{playClick();closeWallpaperModal()});
wallpaperBackdrop.addEventListener('click',e=>{if(e.target===wallpaperBackdrop)closeWallpaperModal()});
wallpaperFileInput.addEventListener('change',async()=>{if(wallpaperFileInput.files&&wallpaperFileInput.files[0])await handleWallpaperImage(wallpaperFileInput.files[0]);wallpaperFileInput.value=''})
wallpaperVideoFileInput.addEventListener('change',async()=>{if(wallpaperVideoFileInput.files&&wallpaperVideoFileInput.files[0])await handleWallpaperVideo(wallpaperVideoFileInput.files[0]);wallpaperVideoFileInput.value=''})
if(wallpaperVolumeInput)wallpaperVolumeInput.addEventListener('input',()=>{setWallpaperVolume(wallpaperTarget,wallpaperVolumeInput.value);if(activeTab===wallpaperTarget)tryPlayWallpaperVideo()});
function applyVideoFps(v){S.videoFps=v==='60'?'60':'30';ls('video-fps',S.videoFps);$$('[data-video-fps]').forEach(b=>b.classList.toggle('active',b.dataset.videoFps===S.videoFps));applyWallpaper()}
function applyVideoQuality(v){S.videoQuality=v==='4k'?'4k':'1080p';ls('video-quality',S.videoQuality);$$('[data-video-quality]').forEach(b=>b.classList.toggle('active',b.dataset.videoQuality===S.videoQuality));applyWallpaper()}
$$('[data-video-fps]').forEach(b=>b.addEventListener('click',()=>{playClick();applyVideoFps(b.dataset.videoFps)}));
$$('[data-video-quality]').forEach(b=>b.addEventListener('click',()=>{playClick();applyVideoQuality(b.dataset.videoQuality)}));
$$('[data-video-fps]').forEach(b=>b.classList.toggle('active',b.dataset.videoFps===S.videoFps));
$$('[data-video-quality]').forEach(b=>b.classList.toggle('active',b.dataset.videoQuality===S.videoQuality));
$('toggle-effects-button').addEventListener('click',()=>applyEffects(S.effects==='on'?'off':'on'));
$('toggle-responses-button').addEventListener('click',()=>applyOptResp(S.optResp==='on'?'off':'on'));
$('toggle-uiopt-button').addEventListener('click',()=>applyUiOpt(S.uiOpt==='on'?'off':'on'));
['user-firstname','user-lastname','user-tone','user-info'].forEach(id=>$(id).addEventListener('input',persistPerso));
(function(){const aiIn=$('ai-name-input'),aiReset=$('ai-name-reset-btn');if(aiIn){aiIn.value=S.aiName||'';aiIn.addEventListener('input',()=>{S.aiName=aiIn.value.trim();ls('ai-name',S.aiName);updateAiName()})}if(aiReset){aiReset.addEventListener('click',()=>{playClick();S.aiName='';ls('ai-name','');if(aiIn)aiIn.value='';updateAiName()})}})();
(function(){const aiLogoChange=$('ai-logo-change-btn'),aiLogoReset=$('ai-logo-reset-btn'),aiLogoPreview=$('ai-logo-preview');function refreshLogoPreview(){if(!aiLogoPreview)return;const mainLogo=$('main-logo');const fallback=mainLogo?mainLogo.dataset.light||mainLogo.src:'';aiLogoPreview.src=S.aiLogo||fallback}if(aiLogoChange){aiLogoChange.addEventListener('click',()=>{playClick();const inp=document.createElement('input');inp.type='file';inp.accept='image/*';inp.onchange=e=>{const f=e.target.files&&e.target.files[0];if(!f)return;const r=new FileReader();r.onload=ev=>{const data=ev.target.result;S.aiLogo=data;ls('ai-logo',data);updateThemedLogos();refreshLogoPreview()};r.readAsDataURL(f)};inp.click()})}if(aiLogoReset){aiLogoReset.addEventListener('click',()=>{playClick();S.aiLogo='';ls('ai-logo','');updateThemedLogos();refreshLogoPreview()})}refreshLogoPreview()})();
['profile-firstname-input','profile-lastname-input','profile-bio-input','profile-instagram-input','profile-tiktok-input','profile-youtube-input','profile-github-input','profile-bluesky-input'].forEach(id=>$(id).addEventListener('input',persistProfileForm));
(function(){const bioIn=$('profile-bio-input'),bioCount=$('profile-bio-count'),bioCounter=$('profile-bio-counter');if(!bioIn||!bioCount)return;function updateBioCounter(){const len=bioIn.value.length;bioCount.textContent=String(len);bioCounter.classList.remove('warning','danger');if(len>900)bioCounter.classList.add('danger');else if(len>750)bioCounter.classList.add('warning')}bioIn.addEventListener('input',updateBioCounter);updateBioCounter()})();
profileEditToggle.addEventListener('click',()=>toggleProfileEditor());
calcTargetTrigger.addEventListener('click',()=>{playClick();calcTargetMenu.classList.contains('open')?closeCalcTargetMenu():openCalcTargetMenu()});
calcTargetMenu.addEventListener('click',e=>{const btn=e.target.closest('[data-ct-value]');if(!btn)return;playClick();applyCalcTarget(btn.dataset.ctValue,false,true);closeCalcTargetMenu()});
if(profileShareProBtn)profileShareProBtn.addEventListener('click',()=>shareProfile(false));
if(profileShareFullBtn)profileShareFullBtn.addEventListener('click',()=>shareProfile(true));
if(profileAvatarMessagesToggle)profileAvatarMessagesToggle.addEventListener('change',()=>{profileSet('showMessageAvatar',profileAvatarMessagesToggle.checked?'on':'off');updateProfileUI();renderMessages()});
voiceInputBtn.addEventListener('click',triggerVoiceInput);
profileAvatarUploadBtn.addEventListener('click',()=>openProfilePicker('avatar'));
profileBannerUploadBtn.addEventListener('click',()=>openProfilePicker('banner'));
if(profilePickerCloseBtn)profilePickerCloseBtn.addEventListener('click',closeProfilePicker);
if(profilePickerBackdrop)profilePickerBackdrop.addEventListener('click',e=>{if(e.target===profilePickerBackdrop)closeProfilePicker()});
profileAvatarRemoveBtn.addEventListener('click',()=>{profileSet('avatar','');loadProfileForm()});
profileBannerRemoveBtn.addEventListener('click',()=>{profileSet('banner','');loadProfileForm()});
profileAvatarFile.addEventListener('change',async()=>{if(profileAvatarFile.files&&profileAvatarFile.files[0])await handleProfileImage(profileAvatarFile.files[0],'avatar');profileAvatarFile.value=''})
profileBannerFile.addEventListener('change',async()=>{if(profileBannerFile.files&&profileBannerFile.files[0])await handleProfileImage(profileBannerFile.files[0],'banner');profileBannerFile.value=''})
cropApplyBtn.addEventListener('click',applyCrop);
cropCancelBtn.addEventListener('click',closeCropper);
cropCloseBtn.addEventListener('click',closeCropper);
cropBackdrop.addEventListener('click',e=>{if(e.target===cropBackdrop)closeCropper()});
cropZoom.addEventListener('input',()=>{if(!cropState)return;cropState.zoom=Math.max(1,Number(cropZoom.value||100)/100);clampCropOffsets();renderCropper()});
cropCanvas.addEventListener('pointerdown',e=>{if(!cropState)return;cropState.dragging=true;cropState.pointerId=e.pointerId;cropState.lastX=e.clientX;cropState.lastY=e.clientY;cropCanvas.classList.add('dragging');try{cropCanvas.setPointerCapture(e.pointerId)}catch{}});
cropCanvas.addEventListener('pointermove',e=>{if(!cropState||!cropState.dragging)return;cropState.offsetX+=e.clientX-cropState.lastX;cropState.offsetY+=e.clientY-cropState.lastY;cropState.lastX=e.clientX;cropState.lastY=e.clientY;clampCropOffsets();renderCropper()});
const releaseCropPointer=e=>{if(!cropState)return;cropState.dragging=false;cropCanvas.classList.remove('dragging');try{if(e&&cropState.pointerId!==null)cropCanvas.releasePointerCapture(cropState.pointerId)}catch{}cropState.pointerId=null};
cropCanvas.addEventListener('pointerup',releaseCropPointer);
cropCanvas.addEventListener('pointercancel',releaseCropPointer);
window.addEventListener('resize',()=>{if(cropState)initCropState();hideProfileAvatarHover(true)});
msgBox.addEventListener('scroll',()=>hideProfileAvatarHover(true));
// Boutons paramètres — fonctionnalités à venir (alertes temporaires)
const manageMemoryButton=$('manage-memory-button'),manageHistoryButton=$('manage-history-button'),releaseRamButton=$('release-ram-button'),updateInfoButton=$('update-info-button');
if(manageMemoryButton)manageMemoryButton.addEventListener('click',()=>{playClick();alert(t('soon'))});
if(manageHistoryButton)manageHistoryButton.addEventListener('click',()=>{playClick();alert(t('soon'))});
if(releaseRamButton)releaseRamButton.addEventListener('click',()=>{playClick();alert(t('soon'))});
if(updateInfoButton)updateInfoButton.addEventListener('click',()=>{playClick();alert(t('soon'))});
if(scaleDownButton)scaleDownButton.addEventListener('click',()=>applyUIScale(S.uiScale-10,true));
if(scaleUpButton)scaleUpButton.addEventListener('click',()=>applyUIScale(S.uiScale+10,true));
['pointerdown','keydown','touchstart'].forEach(evt=>document.addEventListener(evt,tryPlayWallpaperVideo,{passive:true}));
document.addEventListener('visibilitychange',()=>{if(!document.hidden)tryPlayWallpaperVideo()});
$('goat-dev-news-btn').addEventListener('click',()=>{playClick();alert(t('soon'))});
$('goat-dev-about-btn').addEventListener('click',()=>{playClick();alert(t('soon'))});
$('migrate-data-button').addEventListener('click',()=>{playClick();closeSettings();setTimeout(openMigrate,200)});

// ── Modal contact développeur (onglet Aide) ──────────────────
const aideContactBackdrop=$('aide-contact-backdrop');
function openAideContact(){aideContactBackdrop.classList.add('open');document.body.style.overflow='hidden'}
function closeAideContact(){aideContactBackdrop.classList.remove('open');document.body.style.overflow=''}
$('aide-contact-btn').addEventListener('click',()=>{playClick();openAideContact()});
$('aide-contact-close').addEventListener('click',()=>{playClick();closeAideContact()});
// Clic sur le fond pour fermer
aideContactBackdrop.addEventListener('click',e=>{if(e.target===aideContactBackdrop)closeAideContact()});

// Fermeture des dropdowns au clic en dehors
document.addEventListener('click',e=>{if(!(e.target instanceof Element))return;if(!modeMenu.contains(e.target)&&!modeTrigger.contains(e.target))closeMM();if(!styleMenu.contains(e.target)&&!styleTrigger.contains(e.target))closeSM();if(!gadgetMenu.contains(e.target)&&!gadgetTrigger.contains(e.target))closeGM();if(!modelDDMenu.contains(e.target)&&!modelTriggerBtn.contains(e.target))closeModelDD();if(!plusMenu.contains(e.target)&&!composerPlus.contains(e.target))plusMenu.classList.remove('open');if(!calcTargetMenu.contains(e.target)&&!calcTargetTrigger.contains(e.target))closeCalcTargetMenu()});
// ── Barre latérale (Sidebar) ─────────────────────────────────────
const sidebarPanel=$('sidebar-panel'),sidebarOverlay=$('sidebar-overlay');
let sidebarOpen=false;
function openSidebar(){
  sidebarOpen=true;
  if(sidebarPanel){sidebarPanel.classList.add('open');sidebarPanel.setAttribute('aria-hidden','false')}
  if(sidebarOverlay){sidebarOverlay.classList.add('open');sidebarOverlay.setAttribute('aria-hidden','false')}
}
function closeSidebar(){
  sidebarOpen=false;
  if(sidebarPanel){sidebarPanel.classList.remove('open');sidebarPanel.setAttribute('aria-hidden','true')}
  if(sidebarOverlay){sidebarOverlay.classList.remove('open');sidebarOverlay.setAttribute('aria-hidden','true')}
}
// Bouton toggle sidebar (☰)
const sidebarToggleBtn=$('sidebar-toggle-btn');
if(sidebarToggleBtn)sidebarToggleBtn.addEventListener('click',()=>{playClick();sidebarOpen?closeSidebar():openSidebar()});
// Bouton fermer dans la sidebar (×)
const sidebarCloseBtn=$('sidebar-close-btn');
if(sidebarCloseBtn)sidebarCloseBtn.addEventListener('click',()=>{playClick();closeSidebar()});
// Clic sur l'overlay ferme la sidebar
if(sidebarOverlay)sidebarOverlay.addEventListener('click',()=>{closeSidebar()});
// Bouton "Nouvelle discussion" dans la sidebar
const sidebarNewChatBtn=$('sidebar-new-chat-btn');
if(sidebarNewChatBtn)sidebarNewChatBtn.addEventListener('click',async()=>{
  closeSidebar();
  playClick();
  if(!confirm(t('new_chat_confirm')))return;
  statusEl.textContent='...';
  try{
    const p=await apiNewChat();
    messages=p.messages;messagesMeta=p.metas||[];
    refreshWelcomeContent();
    renderMessages();
    statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);
    ta.value='';autoResize();ta.focus();
  }catch(e){statusEl.textContent=e.message}
});
// Bouton "Paramètres" dans la sidebar
const sidebarSettingsBtn=$('sidebar-settings-btn');
if(sidebarSettingsBtn)sidebarSettingsBtn.addEventListener('click',()=>{playClick();closeSidebar();openSettings()});
// ── Système "Créer un fichier" : modale + persistance + menu actions ──
const sfBackdrop=$('sf-modal-backdrop'),sfTitleEl=$('sf-modal-title'),sfInput=$('sf-modal-input'),sfCancel=$('sf-modal-cancel'),sfConfirm=$('sf-modal-confirm');
const sfPopover=$('sf-popover'),sfPopRename=$('sf-popover-rename'),sfPopDelete=$('sf-popover-delete');
const sfFilesContainer=document.querySelector('[data-sidebar-content="files"]');
let sfMode='create',sfActiveId=null,sfMenuTargetId=null,sfMenuTargetEl=null;
function sfLoad(){try{const raw=ls('sidebar-files')||'[]';const arr=JSON.parse(raw);return Array.isArray(arr)?arr:[]}catch(e){return[]}}
function sfSave(arr){ls('sidebar-files',JSON.stringify(arr||[]))}
function sfNewId(){return 'f_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,7)}
function sfOpenModal(mode,id){
  sfMode=mode;sfActiveId=id||null;
  if(mode==='rename'){
    const file=sfLoad().find(f=>f.id===id);
    sfTitleEl.textContent='Renommer le fichier';
    sfConfirm.textContent='Renommer';
    sfInput.value=file?file.name:'';
  }else{
    sfTitleEl.textContent='Nouveau fichier';
    sfConfirm.textContent='Créer';
    sfInput.value='';
  }
  sfBackdrop.classList.add('open');
  sfBackdrop.setAttribute('aria-hidden','false');
  setTimeout(()=>{try{sfInput.focus();sfInput.select()}catch(e){}},30);
}
function sfCloseModal(){sfBackdrop.classList.remove('open');sfBackdrop.setAttribute('aria-hidden','true');sfActiveId=null}
function sfConfirmModal(){
  const name=(sfInput.value||'').trim();
  if(!name){sfInput.focus();return}
  const arr=sfLoad();
  if(sfMode==='rename'&&sfActiveId){
    const idx=arr.findIndex(f=>f.id===sfActiveId);
    if(idx>=0){arr[idx].name=name;sfSave(arr)}
  }else{
    arr.push({id:sfNewId(),name:name,created:Date.now()});
    sfSave(arr);
  }
  sfCloseModal();sfRenderFiles();
}
function sfClosePopover(){
  if(!sfPopover)return;
  sfPopover.classList.remove('open');
  sfPopover.setAttribute('aria-hidden','true');
  if(sfMenuTargetEl)sfMenuTargetEl.classList.remove('menu-open');
  sfMenuTargetId=null;sfMenuTargetEl=null;
}
function sfOpenPopover(itemEl,id){
  sfClosePopover();
  sfMenuTargetId=id;sfMenuTargetEl=itemEl;
  itemEl.classList.add('menu-open');
  sfPopover.classList.add('open');
  sfPopover.setAttribute('aria-hidden','false');
  const r=itemEl.getBoundingClientRect();
  const popW=sfPopover.offsetWidth||180;
  const popH=sfPopover.offsetHeight||80;
  let left=r.right-popW;
  if(left<8)left=8;
  if(left+popW>window.innerWidth-8)left=window.innerWidth-popW-8;
  let top=r.bottom+4;
  if(top+popH>window.innerHeight-8)top=Math.max(8,r.top-popH-4);
  sfPopover.style.left=left+'px';
  sfPopover.style.top=top+'px';
}
function sfRenderFiles(){
  if(!sfFilesContainer)return;
  // Conserver le bouton "Créer un fichier" en tête de liste
  const createBtn=sfFilesContainer.querySelector('#sidebar-create-file-btn');
  sfFilesContainer.innerHTML='';
  if(createBtn)sfFilesContainer.appendChild(createBtn);
  const arr=sfLoad();
  arr.forEach(f=>{
    const row=document.createElement('div');
    row.className='sf-item';
    row.dataset.fileId=f.id;
    row.innerHTML='<svg class="sf-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>'+
      '<span class="sf-item-name"></span>'+
      '<button type="button" class="sf-item-more" aria-label="Options"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="5" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="19" r="1.4"/></svg></button>';
    row.querySelector('.sf-item-name').textContent=f.name;
    const more=row.querySelector('.sf-item-more');
    const opener=e=>{e.stopPropagation();if(sfMenuTargetId===f.id){sfClosePopover();return}sfOpenPopover(row,f.id)};
    row.addEventListener('click',opener);
    more.addEventListener('click',opener);
    sfFilesContainer.appendChild(row);
  });
}
const sidebarCreateFileBtn=$('sidebar-create-file-btn');
if(sidebarCreateFileBtn)sidebarCreateFileBtn.addEventListener('click',e=>{e.stopPropagation();playClick();sfClosePopover();sfOpenModal('create')});
if(sfCancel)sfCancel.addEventListener('click',()=>{playClick();sfCloseModal()});
if(sfConfirm)sfConfirm.addEventListener('click',()=>{playClick();sfConfirmModal()});
if(sfBackdrop)sfBackdrop.addEventListener('click',e=>{if(e.target===sfBackdrop)sfCloseModal()});
if(sfInput)sfInput.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();sfConfirmModal()}else if(e.key==='Escape'){e.preventDefault();sfCloseModal()}});
if(sfPopRename)sfPopRename.addEventListener('click',e=>{e.stopPropagation();playClick();const id=sfMenuTargetId;sfClosePopover();if(id)sfOpenModal('rename',id)});
if(sfPopDelete)sfPopDelete.addEventListener('click',e=>{e.stopPropagation();playClick();const id=sfMenuTargetId;sfClosePopover();if(!id)return;if(!confirm('Supprimer ce fichier ?'))return;const arr=sfLoad().filter(f=>f.id!==id);sfSave(arr);sfRenderFiles()});
document.addEventListener('click',e=>{if(!sfPopover||!sfPopover.classList.contains('open'))return;if(sfPopover.contains(e.target))return;if(sfMenuTargetEl&&sfMenuTargetEl.contains(e.target))return;sfClosePopover()});
window.addEventListener('resize',sfClosePopover);
window.addEventListener('scroll',sfClosePopover,true);
sfRenderFiles();
// Onglets de la sidebar (Fichiers / Historique)
$$('[data-sidebar-tab]').forEach(btn=>btn.addEventListener('click',()=>{
  playClick();
  const tab=btn.dataset.sidebarTab;
  $$('[data-sidebar-tab]').forEach(b=>b.classList.toggle('active',b.dataset.sidebarTab===tab));
  $$('[data-sidebar-content]').forEach(s=>s.hidden=s.dataset.sidebarContent!==tab);
}));
// Recherche dans la sidebar (placeholder — filtrage futur de l'historique)
const sidebarSearch=$('sidebar-search');
if(sidebarSearch)sidebarSearch.addEventListener('input',()=>{/* filtrage historique à implémenter */});
// Bouton profil dans le footer de la sidebar — ouvre l'onglet Profil des paramètres
const sidebarProfileBtn=$('sidebar-profile-btn');
if(sidebarProfileBtn)sidebarProfileBtn.addEventListener('click',()=>{
  playClick();closeSidebar();openSettings();
  // Bascule sur l'onglet Profil si présent
  const _pt=document.querySelector('[data-settings-tab="profile"]');if(_pt)_pt.click();
});

// ──────────────────────────────────────────────────────────────
// Composer : bouton + (Image / Fichier)
// ──────────────────────────────────────────────────────────────
const attachBtn=$('attach-btn'),attachMenu=$('attach-menu'),attachImageBtn=$('attach-image-btn'),attachFileBtn=$('attach-file-btn');
const attachImageInput=$('attach-image-input'),attachFileInput=$('attach-file-input'),attachmentsRow=$('attachments-row');
let attachments=[]; // [{kind:'image'|'file',name,size,type,dataUrl?}]
function fmtSize(n){if(!Number.isFinite(n))return'';const u=['o','Ko','Mo','Go'];let i=0,v=n;while(v>=1024&&i<u.length-1){v/=1024;i++}return (v<10?v.toFixed(1):Math.round(v))+' '+u[i]}
function escAttr(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function renderAttachments(){
  if(!attachmentsRow)return;
  if(!attachments.length){attachmentsRow.hidden=true;attachmentsRow.innerHTML='';return}
  attachmentsRow.hidden=false;
  attachmentsRow.innerHTML=attachments.map((a,i)=>{
    const thumb=a.kind==='image'&&a.dataUrl
      ?`<span class="attachment-thumb"><img src="${escAttr(a.dataUrl)}" alt=""></span>`
      :`<span class="attachment-thumb"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg></span>`;
    return `<div class="attachment-chip" data-att-idx="${i}">${thumb}<div class="attachment-meta"><span class="attachment-name" title="${escAttr(a.name)}">${escAttr(a.name)}</span><span class="attachment-size">${escAttr(fmtSize(a.size))}</span></div><button type="button" class="attachment-remove" data-att-remove="${i}" aria-label="Retirer">×</button></div>`;
  }).join('');
  attachmentsRow.querySelectorAll('[data-att-remove]').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();attachments.splice(+b.dataset.attRemove,1);renderAttachments()}));
}
function readImageFile(file){return new Promise(res=>{const r=new FileReader();r.onload=()=>res(r.result);r.onerror=()=>res(null);r.readAsDataURL(file)})}
async function addAttachmentsFromInput(input,kind){
  const files=Array.from(input.files||[]);input.value='';
  for(const f of files){
    const a={kind,name:f.name,size:f.size,type:f.type||''};
    if(kind==='image'&&/^image\//.test(f.type||'')){a.dataUrl=await readImageFile(f)}
    attachments.push(a);
  }
  renderAttachments();
}
function openAttachMenu(){if(!attachMenu)return;attachMenu.classList.add('open');attachBtn.setAttribute('aria-expanded','true')}
function closeAttachMenu(){if(!attachMenu)return;attachMenu.classList.remove('open');attachBtn.setAttribute('aria-expanded','false')}
if(attachBtn)attachBtn.addEventListener('click',e=>{e.stopPropagation();playClick();attachMenu.classList.contains('open')?closeAttachMenu():openAttachMenu()});
if(attachImageBtn)attachImageBtn.addEventListener('click',()=>{playClick();closeAttachMenu();attachImageInput.click()});
if(attachFileBtn)attachFileBtn.addEventListener('click',()=>{playClick();closeAttachMenu();attachFileInput.click()});
if(attachImageInput)attachImageInput.addEventListener('change',()=>addAttachmentsFromInput(attachImageInput,'image'));
if(attachFileInput)attachFileInput.addEventListener('change',()=>addAttachmentsFromInput(attachFileInput,'file'));
// Ferme le menu si l'on clique à l'extérieur
document.addEventListener('click',e=>{
  if(!attachMenu||!attachMenu.classList.contains('open'))return;
  if(attachMenu.contains(e.target)||(attachBtn&&attachBtn.contains(e.target)))return;
  closeAttachMenu();
});

// Touche Escape — ferme toutes les modales et dropdowns ouverts
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeSidebar();closeMM();closeSM();closeGM();closeModelDD();closeCalcTargetMenu();closeAttachMenu();closeSettings();closeMigrate();closeOverclockModal();closeCropper();closeWallpaperModal();closeAideContact();hideProfileAvatarHover(true);hideTip();
  // Fermetures des nouvelles modales (prévisualisation + connecteurs + menubar)
  if(typeof closePreviewWarning==='function')closePreviewWarning();
  if(typeof closeConnectorsModal==='function')closeConnectorsModal();
  if(typeof closeConnectorsCustom==='function')closeConnectorsCustom();
  if(typeof closeAllMenubar==='function')closeAllMenubar();
}});
// Textarea — redimensionnement auto + limite caractères + son clavier
ta.addEventListener('input',()=>{autoResize();enforceCharLimit();updateCharCounter()});
ta.addEventListener('keydown',e=>{const ign=new Set(['Shift','Control','Alt','Meta','CapsLock','Tab','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Escape']);if(!ign.has(e.key)&&e.key!=='Enter')playKey();if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();form.requestSubmit()}});
// Tooltips data-attribute — liés automatiquement au chargement
$$('[data-tooltip-key]').forEach(el=>bindTip(el,el.dataset.tooltipKey));
bindTip(voiceInputBtn,'Micro vocal : Win + H sur Windows, sinon ouverture de Wispr Flow.');

// ── Initialisation au démarrage ───────────────────────────────────
// Ordre important : charger les préférences AVANT d'appliquer les traductions
// pour que la langue correcte soit déjà dans S.lang lors du premier rendu.
loadPerso();loadProfileForm();toggleProfileEditor(false);showTab(ls('settings-tab')||'general');
document.body.dataset.theme=S.theme;document.body.dataset.effects=S.effects;document.body.dataset.textsize=S.textSize;document.body.dataset.aifont=S.aifont;document.body.dataset.userfont=S.userfont;document.body.dataset.accent=normalizeAccent(S.accent);
applyLang(S.lang,false);applyTheme(S.theme,false);applyEffects(S.effects,false);applyTextSize(S.textSize,false);applyUIScale(S.uiScale,false);applyAccent(S.accent,false);
applyOptResp(S.optResp,false);applyCalcTarget(S.calcTarget,false);applyUiOpt(S.uiOpt,false);
applyKbSound(S.kbSound,false);applyKbStyle(S.kbStyle,false);applyClickSound(S.clickSound,false);applyClickStyle(S.clickStyle,false);applyAiSound(S.aiSound,false);
// ── Style d'interface, transparence, teinte, boutons 8 bits, effet IA ────
applyUiStyle(S.uiStyle,false);applyGlassTransparency(S.glassTransparency,false);applyGlassTint(S.glassTint,false);applyPixelButtons(S.pixelButtons,false);applyAiTyping(S.aiTyping,false);applyTypingStyle(S.aiTypingStyle,false);applySendEffects(S.sendEffects,false);applyReflexBoost(S.reflexBoost,false);
// ── Modèles personnalisés : normalisation de l'état au démarrage ──
// Si l'option globale est désactivée, on purge l'éventuel modèle actif.
// Si l'id actif ne correspond plus à aucun modèle (storage corrompu),
// on retombe également sur le modèle par défaut.
if(S.otherModelsOn!=='on'){S.activeCustomModel='';ls('active-custom-model','')}
if(S.activeCustomModel&&!cmGet(S.activeCustomModel)){S.activeCustomModel='';ls('active-custom-model','')}
if(S.model===CUSTOM_MODEL_SENTINEL&&!cmHasCustomActive()){S.model=defs.model;ls('model',S.model)}
applyOtherModelsOn(S.otherModelsOn,false);
updateSndVis();enforceMode();renderModes();updateModeUI();renderStyles();updateStyleUI();renderGadgets();updateGadgetUI();renderModelDD();updateCustomModelTriggerUI();renderCustomModelsMenu();updatePrivateChatLabels();updateThemedLogos();autoResize();renderMessages();renderSheets();updatePerf();
applyAiFont(S.aifont,false);applyUserFont(S.userfont,false);updateOverclockUI();updateCharCounter();updateWallpaperPreviews();
setActiveTab(activeTab,false);applyWallpaper();updateAiName();ta.focus(); // Focus textarea au démarrage

// ── Top Tab Bar (Chat / Goat Code) ──
if(tabChat){
  tabChat.addEventListener('click',()=>{
    playClick();
    if(activeTab!=='chat'){
      switchTabWithReset('chat');
      return;
    }
    const menu=modelDDMenu;
    if(menu.classList.contains('open')){
      menu.classList.remove('open');
      tabChat.setAttribute('aria-expanded','false');
    }else{
      menu.classList.add('open');
      tabChat.setAttribute('aria-expanded','true');
    }
  });
}
if(tabCoworking){
  tabCoworking.addEventListener('click',()=>{
    playClick();
    switchTabWithReset('coworking');
  });
}
// Fermer le model dropdown quand on clique ailleurs
document.addEventListener('click',function(e){if(tabChat&&modelDDMenu&&!tabChat.contains(e.target)&&!modelDDMenu.contains(e.target)){modelDDMenu.classList.remove('open');tabChat.setAttribute('aria-expanded','false')}});

// ──────────────────────────────────────────────────────────────
// Toggle "Version de prévisualisation" — active / désactive
// les fonctions expérimentales sans toucher au DOM (CSS toggle).
// ──────────────────────────────────────────────────────────────
const previewToggleInput=$('preview-toggle-input');
const previewWarningBackdrop=$('preview-warning-backdrop');
const previewWarningConfirm=$('preview-warning-confirm');
const previewWarningCancel=$('preview-warning-cancel');
function applyPreviewMode(state){
  // state : 'on' ou 'off'
  const v=state==='off'?'off':'on';
  S.preview=v;
  ls('preview',v);
  document.body.dataset.preview=v;
  if(previewToggleInput)previewToggleInput.checked=(v==='on');
  // Ferme la sidebar si on bascule en mode off et qu'elle est ouverte
  if(v==='off'&&typeof closeSidebar==='function')closeSidebar();
  // Sortir du chat privé si on bascule en off
  if(v==='off'&&S.privateChat&&typeof exitPrivateChat==='function')exitPrivateChat();
}
function openPreviewWarning(){if(previewWarningBackdrop)previewWarningBackdrop.classList.add('open')}
function closePreviewWarning(){if(previewWarningBackdrop)previewWarningBackdrop.classList.remove('open')}
if(previewToggleInput){
  previewToggleInput.addEventListener('change',()=>{
    playClick();
    if(previewToggleInput.checked){
      // Activation → on demande confirmation puis on applique
      previewToggleInput.checked=false; // on attend la confirmation
      openPreviewWarning();
    }else{
      // Désactivation → immédiate
      applyPreviewMode('off');
    }
  });
}
if(previewWarningConfirm)previewWarningConfirm.addEventListener('click',()=>{playClick();closePreviewWarning();applyPreviewMode('on')});
if(previewWarningCancel)previewWarningCancel.addEventListener('click',()=>{playClick();closePreviewWarning();applyPreviewMode('off')});
if(previewWarningBackdrop)previewWarningBackdrop.addEventListener('click',e=>{if(e.target===previewWarningBackdrop){closePreviewWarning();applyPreviewMode('off')}});

// État initial : "on" par défaut sauf si l'utilisateur a explicitement désactivé.
applyPreviewMode(ls('preview')||'on');

// ──────────────────────────────────────────────────────────────
// Onglet Connecteurs — modale "Aucun connecteur" + bouton custom
// ──────────────────────────────────────────────────────────────
const connectorsModalBackdrop=$('connectors-modal-backdrop');
const connectorsModalClose=$('connectors-modal-close');
const connectorsAddBtn=$('connectors-add-btn');
const connectorsAddCustomBtn=$('connectors-add-custom-btn');
const connectorsCustomBackdrop=$('connectors-custom-backdrop');
const connectorsCustomClose=$('connectors-custom-close');
const connectorsCustomOk=$('connectors-custom-ok');
function openConnectorsModal(){if(connectorsModalBackdrop)connectorsModalBackdrop.classList.add('open')}
function closeConnectorsModal(){if(connectorsModalBackdrop)connectorsModalBackdrop.classList.remove('open')}
function openConnectorsCustom(){if(connectorsCustomBackdrop)connectorsCustomBackdrop.classList.add('open')}
function closeConnectorsCustom(){if(connectorsCustomBackdrop)connectorsCustomBackdrop.classList.remove('open')}
if(connectorsAddBtn)connectorsAddBtn.addEventListener('click',()=>{playClick();openConnectorsModal()});
if(connectorsModalClose)connectorsModalClose.addEventListener('click',()=>{playClick();closeConnectorsModal()});
if(connectorsModalBackdrop)connectorsModalBackdrop.addEventListener('click',e=>{if(e.target===connectorsModalBackdrop)closeConnectorsModal()});
if(connectorsAddCustomBtn)connectorsAddCustomBtn.addEventListener('click',()=>{playClick();closeConnectorsModal();openConnectorsCustom()});
if(connectorsCustomClose)connectorsCustomClose.addEventListener('click',()=>{playClick();closeConnectorsCustom()});
if(connectorsCustomOk)connectorsCustomOk.addEventListener('click',()=>{playClick();closeConnectorsCustom()});
if(connectorsCustomBackdrop)connectorsCustomBackdrop.addEventListener('click',e=>{if(e.target===connectorsCustomBackdrop)closeConnectorsCustom()});

// ──────────────────────────────────────────────────────────────
// Barre de menu (Fichier / Édition / Aide)
// ──────────────────────────────────────────────────────────────
const menuFileBtn=$('menu-file-btn'),menuEditBtn=$('menu-edit-btn'),menuHelpBtn=$('menu-help-btn');
const menubarItems=[menuFileBtn,menuEditBtn,menuHelpBtn].filter(Boolean);
function closeAllMenubar(){menubarItems.forEach(b=>{b.classList.remove('open');b.setAttribute('aria-expanded','false')})}
function toggleMenubar(btn){
  const isOpen=btn.classList.contains('open');
  closeAllMenubar();
  if(!isOpen){btn.classList.add('open');btn.setAttribute('aria-expanded','true')}
}
menubarItems.forEach(btn=>btn.addEventListener('click',e=>{e.stopPropagation();playClick();toggleMenubar(btn)}));
// Survol : si un item est déjà ouvert et qu'on survole un autre, on bascule.
menubarItems.forEach(btn=>btn.addEventListener('mouseenter',()=>{
  const anyOpen=menubarItems.some(b=>b.classList.contains('open'));
  if(anyOpen&&!btn.classList.contains('open')){closeAllMenubar();btn.classList.add('open');btn.setAttribute('aria-expanded','true')}
}));
// Clic en dehors → fermeture
document.addEventListener('click',e=>{
  if(!e.target||!e.target.closest)return;
  if(!e.target.closest('#app-menubar'))closeAllMenubar();
});

// Actions des items de menu
async function handleMenubarAction(action){
  closeAllMenubar();
  switch(action){
    case 'open-location':
      try{
        const r=await fetch('/api/open_app_folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
        const p=await r.json();
        if(!p||!p.ok)alert((p&&p.error)||t('soon'));
      }catch(err){alert(t('soon'))}
      break;
    case 'open-settings':
      openSettings();
      break;
    case 'new-chat':
      if(!confirm(t('new_chat_confirm')))return;
      try{
        statusEl.textContent='...';
        const p=await apiNewChat();
        messages=p.messages;messagesMeta=p.metas||[];refreshWelcomeContent();renderMessages();
        statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);
        ta.value='';autoResize();ta.focus();
      }catch(e){statusEl.textContent=e.message}
      break;
    case 'undo':document.execCommand('undo');break;
    case 'redo':document.execCommand('redo');break;
    case 'cut':document.execCommand('cut');break;
    case 'copy':document.execCommand('copy');break;
    case 'paste':
      try{
        if(navigator.clipboard&&navigator.clipboard.readText){
          const text=await navigator.clipboard.readText();
          if(document.activeElement&&'value' in document.activeElement){
            const el=document.activeElement;
            const start=el.selectionStart||0,end=el.selectionEnd||0;
            el.value=el.value.substring(0,start)+text+el.value.substring(end);
            el.selectionStart=el.selectionEnd=start+text.length;
            el.dispatchEvent(new Event('input',{bubbles:true}));
          }
        }else{document.execCommand('paste')}
      }catch(e){/* l'API clipboard nécessite une permission */}
      break;
    case 'select-all':
      if(document.activeElement&&document.activeElement.select){document.activeElement.select()}
      else{document.execCommand('selectAll')}
      break;
    case 'find':
      // Focus la barre de recherche de la sidebar si dispo, sinon ouvre la sidebar
      if(typeof openSidebar==='function')openSidebar();
      setTimeout(()=>{const s=$('sidebar-search');if(s){s.focus();s.select&&s.select()}},120);
      break;
    case 'contact-dev':
      // Ouvre la même modale que dans Paramètres → Aide → Contacter
      if(typeof openAideContact==='function')openAideContact();
      break;
    case 'open-doc':
      // Documentation du projet — placeholder, rien pour le moment.
      break;
  }
}
document.querySelectorAll('[data-menu-action]').forEach(b=>{
  b.addEventListener('click',e=>{e.stopPropagation();playClick();handleMenubarAction(b.dataset.menuAction)});
});

}();
