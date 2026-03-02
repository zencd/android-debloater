function handleFetch(fetchPromise, onSuccess, doAlert) {
  doAlert = (typeof doAlert === 'undefined') ? true : doAlert
  showLoader()
  fetchPromise.then(async (response) => {
    const data = await response.json();
    hideLoader()
    if (!response.ok) {
      console.log('Error', response.status, data)
      if (doAlert) {
        toast(`Error: ${data.message}`, 'toastError')
      }
      throw new Error('HTTP error: ' + response.status);
    }
    return data
  })
  .then(data => {
    console.log('Received data:', data);
    if (onSuccess) {
      try {
        onSuccess(data)
      } catch(exc) {
        console.error('onSuccess handler: failed', exc)
      }
    }
  })
  .catch(error => {
    // error processed already
    hideLoader()
  });
}

function loadUad() {
  handleFetch(fetch('/loadUad'), function(data) {
    const cls = data.ok ? 'toastOk' : 'toastError'
    toast(data.msg, cls)
  })
}

function updatePackagePrefs(pakName, action, onSuccess) {
  handleFetch(
    fetch(`/changePackageResolution?package=${pakName}&action=${action}`),
    onSuccess
  )
}

function loadUserPrefs(doAlert) {
  const safety = window.localStorage.getItem('packageFilter') || ''
  handleFetch(
    fetch(`/packages?filter=${safety}`),
    onPackagesReceived,
    doAlert
  )
}

let gDebloatPackages = []

function onPackagesReceived(data) {
  // todo если убрать data, код не будет работать, но и никакой ошибки не будет х_х
  gDebloatPackages = []
  $debloatUsages.forEach(elem => elem.style.display = data.packages.length === 0 && elem.dataset.lang === gLang ? 'block' : 'none') // hide help
  if (data.warnMsg) toast(data.warnMsg, 'toastWarn')
  $deviceTitle.innerText = data.deviceTitle
  $cards.innerText = ''
  let i = 0
  for (const pakData of data.packages) {
    if (i === 0) $cards.innerText = ''
    const action = pakData['action']
    const pakName = pakData['package']
    const pakTitle = pakData['title'] || ''
    const icon = pakData['icon'] || ''
    const description = pakData['description']
    const removal = pakData['removal'] || ''
    const status = pakData['status'] || ''
    const tags = pakData['tags'] || []
    if (removal) tags.push(removal)
    addCard(pakName, pakTitle, icon, description, tags, action, status)
    gDebloatPackages.push(pakName)
    i++
  }
  $packageFilter.querySelectorAll('option').forEach($option => {
    //if (!$option.selected) return
    let text = $option.innerText.replace(/:\s*\d+/, '') // cut number of packages
    text = $option.selected ? `${text}: ${data.packages.length}` : text // add number of packages
    if (text !== $option.innerText) {
      $option.innerText = text
    }
  })
}

function deleteUnwanted() {
  handleFetch(fetch('/debloat'), function(data) {
    if (data.oks === 0 && data.fails === 0) {
      toast('Nothing to do', 'toastOk')
    } else {
      const cls = data.fails === 0 ? 'toastOk' : 'toastError'
      toast(`Packages deleted: ${data.oks}.\nFailed to delete: ${data.fails}.`, cls)
    }
  })
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function addCard(package, title, icon, description, tags, action, status) {
  tags = tags || ['?']
  const cardClass = action === 'keep' ? 'keep' : action === 'del' ? 'del' : action === 'review' ? 'review' : ''
  const titleOpt = title ? `<div class="title" translate="no">${escapeHtml(title)}</div>` : ''

  const labelNew = gLang === 'en' ? 'N/A' : 'Нет'
  const labelKeep = gLang === 'en' ? 'Keep' : 'Оставить'
  const labelReview = gLang === 'en' ? 'Review' : 'Ревью'
  const labelDebloat = gLang === 'en' ? 'Debloat' : 'Удалить'

  const labelEnabled = gLang === 'en' ? 'Enabled:' : 'Активно:'
  const labelDisabled = gLang === 'en' ? 'Disabled:' : 'Отключено:'
  const labelUninstalled = gLang === 'en' ? 'Uninstalled:' : 'Удалено:'

  const labelReinstall = gLang === 'en' ? 'Reinstall' : 'Установить'
  const labelDisable = gLang === 'en' ? 'Disable' : 'Отключить'
  const labelEnable = gLang === 'en' ? 'Enable' : 'Включить'
  const labelUninstall = gLang === 'en' ? 'Uninstall' : 'Удалить'

  const labelResolution = gLang === 'en' ? 'Resolution' : 'Решение'

  if (gLang === 'ru' && description === 'User installed this app (likely)') {
    description = 'Пользовательское приложение (вероятно)'
  }

  const html = `
    <article class="card ${cardClass}">
      <div class="package" translate="no"><span>${escapeHtml(package)}</span></div>
      ${titleOpt}
      <div class="description">${escapeHtml(description || '-')}</div>
      <div class="meta">
        <div class="badges">
        </div>
        <div class="actions">
          <select data-package="${package}">
            <optgroup label="${labelResolution}:">
            <option value="new">${labelNew}</option>
            <option value="keep" ${action === 'keep' ? 'selected' : ''}>${labelKeep}</option>
            <option value="review" ${action === 'review' ? 'selected' : ''}>${labelReview}</option>
            <option value="del" ${action === 'del' ? 'selected' : ''}>${labelDebloat}</option>
            </optgroup>
          </select>
        </div>
      </div>
    </article>
  `;

  const template = document.createElement('template');
  template.innerHTML = html.trim();
  const $card = template.content.firstElementChild;
  if (icon) {
    $card.style.backgroundImage = `url("/appIcon?file=${icon}")`
    $card.style.backgroundRepeat = 'no-repeat'
    $card.style.backgroundPosition = 'right 13px top 6px'
    $card.style.backgroundSize = '30px 30px'
  }
  for (var tag of tags) {
    const $tag = document.createElement('span')
    $tag.innerText = tag
    $tag.classList.add('badge')
    //if (tag !== 'Recommended' && tag !== 'User') {
    //  $tag.classList.add('system')
    //}
    $card.querySelector('.badges').appendChild($tag)
  }

  const packageFilter = window.localStorage.getItem('packageFilter')
  if (status == 'uninstalled') {
    addActionOptionToCard($card, 'reinstall', labelReinstall, labelUninstalled)
  } else if (status == 'enabled') {
    addActionOptionToCard($card, 'disable', labelDisable, labelEnabled)
    addActionOptionToCard($card, 'uninstall', labelUninstall, labelEnabled)
  } else if (status == 'disabled') {
    addActionOptionToCard($card, 'enable', labelEnable, labelDisabled)
    addActionOptionToCard($card, 'uninstall', labelUninstall, labelDisabled)
  }

  $cards.appendChild($card)
  $card.querySelector('select').addEventListener('change', onActionChange)
}

function addActionOptionToCard($card, value, actionTitle, groupTitle) {
  const $select = $card.querySelector('select')
  let $optgroup2 = $select.querySelector('optgroup:nth-of-type(2)')
  if (!$optgroup2) {
    $optgroup2 = document.createElement('optgroup')
    $select.appendChild($optgroup2)
  }
  $select.setAttribute('data-prev-value', $select.value)
  $optgroup2.setAttribute('label', groupTitle)
  $optionUninstall = document.createElement('option')
  $optionUninstall.setAttribute('value', value)
  $optionUninstall.innerText = actionTitle
  $optgroup2.appendChild($optionUninstall)
}

function onActionChange(e) {
  const package = e.target.getAttribute('data-package')
  const action = e.target.value
  const prevAction = e.target.getAttribute('data-prev-value') || ''

  if (action === 'uninstall') {
    e.target.value = prevAction // select's value shouldn't change
    handleFetch(fetch(`/changePackageStatus?package=${package}&action=uninstall`), function(data) {
      const cls = data.ok ? 'toastOk' : 'toastError'
      toast(data.msg, cls)
    })
    return
  }

  if (action === 'reinstall') {
    e.target.value = prevAction // select's value shouldn't change
    handleFetch(fetch(`/changePackageStatus?package=${package}&action=reinstall`), function(data) {
      const cls = data.ok ? 'toastOk' : 'toastError'
      toast(data.msg, cls)
    })
    return
  }

  if (action === 'enable') {
    e.target.value = prevAction // select's value shouldn't change
    handleFetch(fetch(`/changePackageStatus?package=${package}&action=enable`), function(data) {
      const cls = data.ok ? 'toastOk' : 'toastError'
      toast(data.msg, cls)
    })
    return
  }

  if (action === 'disable') {
    e.target.value = prevAction // select's value shouldn't change
    handleFetch(fetch(`/changePackageStatus?package=${package}&action=disable`), function(data) {
      const cls = data.ok ? 'toastOk' : 'toastError'
      toast(data.msg, cls)
    })
    return
  }

  let $node = e.target
  let $article = null
  while ($node) {
    if ($node.tagName.toLowerCase() === 'article') {
      break
    }
    $node = $node.parentNode
  }
  updatePackagePrefs(package, action, function() {
    if ($node) {
      $node.classList.remove('new')
      $node.classList.remove('keep')
      $node.classList.remove('review')
      $node.classList.remove('del')
      $node.classList.add(action)
    }
  })
}

function backupAppApks() {
  handleFetch(fetch('/backupAppApks'), function(data) {
      if (data.msg) {
        toast(`No backup performed.\n${data.msg}`)
      } else {
        alert(`Backup complete. Apps downloaded: ${data.numAppsDownloaded}.`)
      }
    }
  )
}

function backupAppPerms() {
  handleFetch(fetch('/backupAppPerms'), function(data) {
      if (data.msg) {
        toast(`No backup performed.\n${data.msg}`)
      } else {
        alert(`Backup complete. Permissions written: ${data.numPermWritten}.`)
      }
    }
  )
}

function ajaxCallRestoreApp(package) {
  return fetch(`/restoreApp?package=${package}`).then(r => r.json());
}

async function restoreApps() {
  try {
    showLoader()
    const localAppsResp = await fetch('/loadLocalApps').then(r => r.json());
    for (var packageInfo of localAppsResp.packages) {
      const package = packageInfo[0]
      const installedAlready = packageInfo[1]
      if (!installedAlready) {
        const restoreResp = await ajaxCallRestoreApp(package)
        if (restoreResp.ok) {
          const $li = $localAppsList.querySelector(`[data-package="${package}"]`)
          if ($li) $li.classList.add('installed')
          toast(`App restored: ${package}.`, 'toastOk')
        } else {
          toast(`Failed to restore: ${package}.`, 'toastError')
        }
      }
    }
  } finally {
    hideLoader()
  }
}

async function restoreAppPerms() {
  try {
    showLoader()
    const response = await fetch('/restoreAppPermissions')
    const permResp = await response.json()
    if (!response.ok) {
      toast(`${permResp.message}`, 'toastError')
      return
    }
    console.log('Received data:', permResp)
    if (permResp.fails === 0) {
      toast(`Permissions set: ${permResp.oks}.`, 'toastOk')
    } else {
      toast(`Permissions set: ${permResp.oks}. Failed to set: ${permResp.fails}.`, 'toastError')
    }
  } finally {
    hideLoader()
  }
}

let gInstalledPackages = []
let gNotInstalledPackages = []

function loadLocalApps() {
  handleFetch(fetch('/loadLocalApps'), function(data) {
    $backupUsages.forEach(elem => elem.style.display = data.packages.length === 0 && elem.dataset.lang === gLang ? 'block' : 'none') // hide help
    gInstalledPackages = []
    gNotInstalledPackages = []
    if (data.warnMsg) toast(data.warnMsg, 'toastWarn')
    $deviceTitle.innerText = data.deviceTitle
    $localAppsList.innerText = ''
    for (var packageInfo of data.packages) {
      const packageName = packageInfo[0]
      const installedAlready = packageInfo[1]
      const title = packageInfo[2]
      const $li = document.createElement('li')
      $li.innerHTML = packageName
      if (title) $li.innerHTML += ` <span class="title">- ${title}</span>`
      $li.setAttribute('data-package', packageName)
      if (installedAlready) {
        $li.classList.add('installed')
        gInstalledPackages.push(packageName)
      } else {
        gNotInstalledPackages.push(packageName)
      }
      $li.innerHTML += '<span class="comment"> — to install</span>'
      $localAppsList.appendChild($li)
    }
  })
}

function readAppMeta() {
  handleFetch(fetch('/readAppMeta'), function(data) {
    const className = data.fails > 0 ? 'toastWarn' : 'toastOk'
    toast(`Successfully read meta for ${data.oks} apps. Failed for ${data.fails}.`, className)
  })
}

function loadSettings() {
  handleFetch(fetch('/settings'), function(data) {
    const filesDoLink = ['appProfileFolder',
                         'userDebloatFile',
                         'communityDebloatFile',
                         'communityDebloatUrl',
                         'auditFile',
                         'iconCacheFolder',
                         'appRepo',
                         'venv']
    const filesNoLink = ['pythonVersion']
    const allFiles = filesDoLink.concat(filesNoLink)
    for (let file of allFiles) {
      const $elem = document.querySelector(`.topNavTab[data-tab="settings"] .${file}`)
      const value = data[file]
      if (value.startsWith('https:')) {
        $elem.innerHTML = `<a href="${value}" target="_blank">${escapeHtml(value)}</a>`
      } else {
        if (filesNoLink.includes(file)) {
          $elem.textContent = value
        } else {
          $elem.innerHTML = `<a href="/openFile?what=${encodeURIComponent(file)}" onclick="openFile(event, this)">${escapeHtml(value)}</a>`
        }
      }
    }
  })
}

function onLanguageChange(event, elem) {
  window.localStorage.setItem('appLang', elem.value)
  document.body.dataset.lang = elem.value
  gLang = elem.value
  window.location.reload() // bcs <select> does not change lang automatically
}

function openFile(event, elem) {
  event.preventDefault()
  handleFetch(fetch(elem.getAttribute('href')), function(data) {
  })
}

async function copyAppsToClipboard(e) {
  let text = ''
  if (gInstalledPackages.length > 0) {
    if (text) text += '\n\n'
    text += 'Installed:\n\n'
    text += gInstalledPackages.join('\n')
  }
  if (gNotInstalledPackages.length > 0) {
    console.log('gNotInstalledPackages', gNotInstalledPackages.length)
    if (text) text += '\n\n'
    text += 'Not installed:\n\n'
    text += gNotInstalledPackages.join('\n')
  }
  await navigator.clipboard.writeText(text)
  toast('Packages copied to clipboard', 'toastOk')
}

async function copyDebloatPackagesToClipboard(e) {
  const text = gDebloatPackages.join('\n')
  await navigator.clipboard.writeText(text)
  toast('Packages copied to clipboard', 'toastOk')
}

function showLoader() {
  $loaderOverlay.classList.remove('hidden');
  document.body.style.overflow = 'hidden'; // disable scrolling
}

function hideLoader() {
  $loaderOverlay.classList.add('hidden');
  document.body.style.overflow = ''; // enable scrolling
}

function toast(text, className, duration) {
  className = className || 'toastError'
  duration = duration || 6000
  const t = Toastify({
    text: text,
    duration: duration,
    newWindow: true,
    close: true,
    className: className,
  })
  t.showToast();
}

const log = console.log
const $cards = document.querySelector('.cards')
const $loadUad = document.getElementById('loadUad')
const $reloadUserPrefs = document.getElementById('reloadUserPrefs')
const $reloadApps = document.getElementById('reloadApps')
const $deviceTitle = document.getElementById('deviceTitle')
const $deleteUnwanted = document.getElementById('deleteUnwanted')
const $localAppsList = document.getElementById('localAppsList')
const $loaderOverlay = document.getElementById('loader-overlay')
const $packageFilter = document.getElementById('packageFilter')
const $menuDebloat = document.getElementById('menuDebloat')
const $readAppMeta = document.getElementById('readAppMeta')
const $menuInstall = document.getElementById('menuInstall')
const $tabDebloat = document.getElementById('tabDebloat')
const $tabInstall = document.getElementById('tabInstall')
const $topMenuItems = [$menuDebloat, $menuInstall]
const $copyDebloatPackages = document.getElementById('copyDebloatPackages')
const $copyAppNames = document.getElementById('copyAppNames')
const $backupMenu = document.getElementById('backupMenu')
const $restoreMenu = document.getElementById('restoreMenu')
const $debloatUsages = document.querySelectorAll('#tabDebloat .usage')
const $backupUsages = document.querySelectorAll('#tabInstall .usage')


if ($loadUad) $loadUad.addEventListener('click', loadUad)
if ($reloadUserPrefs) $reloadUserPrefs.addEventListener('click', function() { loadUserPrefs(true) })
if ($deleteUnwanted) $deleteUnwanted.addEventListener('click', deleteUnwanted)
if ($reloadApps) $reloadApps.addEventListener('click', loadLocalApps)
if ($readAppMeta) $readAppMeta.addEventListener('click', readAppMeta)
$copyDebloatPackages.addEventListener('click', copyDebloatPackagesToClipboard)
$copyAppNames.addEventListener('click', copyAppsToClipboard)

$backupMenu.addEventListener('change', function(e) {
  const value = e.target.value
  if (value === 'backupApps') {
    backupAppApks()
  } else if (value === 'backupPermissions') {
    backupAppPerms()
  }
  e.target.value = ''
  e.target.blur()
})

restoreMenu.addEventListener('change', function(e) {
  const value = e.target.value
  if (value === 'restoreApps') {
    restoreApps()
  } else if (value === 'restorePermissions') {
    restoreAppPerms()
  }
  e.target.value = ''
  e.target.blur()
})

///////////////////// TABS

const $menuItems = document.querySelectorAll('.topNav a')
const $menuItemsFirst = $menuItems[0]
const $tabContents = document.querySelectorAll('.topNavTab')

const tabActions = {
  debloat: () => loadUserPrefs(false),
  backup: () => loadLocalApps(),
  settings: () => loadSettings(),
}

function switchTab(tabName) {
  // highlight current tab
  $menuItems.forEach(item => item.classList.toggle('current', item.dataset.tab === tabName))
  // make current tab content visible
  $tabContents.forEach(content => content.style.display = content.dataset.tab === tabName ? 'block' : 'none')
  // perform tab-specific action
  const action = tabActions[tabName]
  if (action) action()
  // change hash
  if ($menuItemsFirst.dataset.tab === tabName) {
    history.pushState("", document.title, window.location.pathname)
  } else {
    window.location.hash = tabName
  }
}

function autoSelectTabByUrl() {
  if (window.location.hash) {
    switchTab(window.location.hash.substring(1))
  } else {
    switchTab($menuItemsFirst.dataset.tab)
  }
}

$menuItems.forEach(item => {
  item.addEventListener('click', function (e) {
    e.preventDefault()
    if (this.classList.contains('current')) return
    switchTab(this.dataset.tab)
  })
})

function escapeHtml(str) {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

/////////////////////

if ($packageFilter) {
  const packageFilter = window.localStorage.getItem('packageFilter')
  if (packageFilter) {
    $packageFilter.value = packageFilter
  }
  $packageFilter.addEventListener('change', function(e) {
    const value = e.target.value
    window.localStorage.setItem('packageFilter', value)
    loadUserPrefs(false)
  })
}

function setupI18N() {
  if (gLang !== 'en') {
    const $selects = document.querySelectorAll('select[data-tr]')
    for (let i = 0; i < $selects.length; i++) {
      setupSelectI18N($selects[i])
    }
  }
}

function setupSelectI18N($select) {
  const $options = $select.querySelectorAll('option[data-tr]')
  for (let j = 0; j < $options.length; j++) {
    const text = $options[j].getAttribute('data-tr')
    if (text) $options[j].innerHTML = text
  }
  const $optGroups = $select.querySelectorAll('optgroup[data-tr]')
  for (let j = 0; j < $optGroups.length; j++) {
    const text = $optGroups[j].getAttribute('data-tr')
    $optGroups[j].setAttribute('label', text)
  }
}

document.addEventListener("DOMContentLoaded", function() {
  autoSelectTabByUrl()
  tippy('[title]', {
    content: (elem) => {
      const override = gLang === 'ru' ? elem.getAttribute('data-tr') : ''
      return override || elem.getAttribute('title')
    },
    onCreate(instance) {
      instance.reference.removeAttribute('title')
    },
  })
  setupI18N()
  document.getElementById('appLangSelect').value = gLang
})
