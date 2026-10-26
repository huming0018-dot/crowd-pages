/* macOS JXA: read only Chrome registration metadata, never cookies or browser APIs. */
ObjC.import('Foundation');
function run(args) {
  var extensionID = 'licijehcpohikchlnkbpjdjdfkcocndg';
  var expectedKey = '@EXTENSION_KEY@';
  var fm = $.NSFileManager.defaultManager;
  function fail(reason) { throw new Error(reason); }
  function object(value) { return value && typeof value === 'object' && !Array.isArray(value); }
  function fileInfo(path) {
    var value = ObjC.deepUnwrap(fm.attributesOfItemAtPathError(path, null));
    if (!value) {
      var split = path.lastIndexOf('/'), parent = path.substring(0, split) || '/';
      if (path === parent) fail('browser_inventory_unavailable');
      var parentInfo = fileInfo(parent);
      if (!parentInfo) return undefined;
      if (parentInfo.NSFileType !== 'NSFileTypeDirectory') fail('browser_inventory_unavailable');
      var siblings = ObjC.deepUnwrap(fm.contentsOfDirectoryAtPathError(parent, null));
      if (!Array.isArray(siblings) || siblings.indexOf(path.substring(split + 1)) !== -1) fail('browser_inventory_unavailable');
    }
    return value;
  }
  function exists(path) { return fileInfo(path) != null; }
  function normalize(path) { return ObjC.unwrap($(path).stringByStandardizingPath); }
  function attributes(path) {
    var result = fileInfo(path);
    if (!result) fail('browser_inventory_unavailable');
    if (result.NSFileType === 'NSFileTypeSymbolicLink') fail('browser_inventory_unavailable');
    return result;
  }
  function read(path) {
    var info = attributes(path);
    if (info.NSFileType !== 'NSFileTypeRegular' || Number(info.NSFileSize) > 67108864) fail('browser_inventory_unavailable');
    var content = $.NSString.stringWithContentsOfFileEncodingError(path, $.NSUTF8StringEncoding, null);
    var text = ObjC.unwrap(content);
    if (typeof text !== 'string') fail('browser_inventory_unavailable');
    var value = JSON.parse(text);
    if (!object(value)) fail('browser_inventory_unavailable');
    return value;
  }
  function scan(root, expected, passive, bound) {
    var found = 0;
    if (!exists(root)) return 'clear';
    if (attributes(root).NSFileType !== 'NSFileTypeDirectory') fail('browser_inventory_unavailable');
    var listing = fm.contentsOfDirectoryAtPathError(root, null);
    var profiles = ObjC.deepUnwrap(listing);
    if (!Array.isArray(profiles)) fail('browser_inventory_unavailable');
    profiles.sort();
    for (var p = 0; p < profiles.length; p++) {
      var profile = root + '/' + profiles[p], paths = [], versions = [];
      var profileInfo = fileInfo(profile);
      if (!profileInfo) fail('browser_inventory_unavailable');
      if (profileInfo.NSFileType === 'NSFileTypeSymbolicLink') {
        if (/^(Default|Profile .+|Guest Profile|System Profile)$/.test(profiles[p]) || fm.fileExistsAtPath(profile + '/Preferences') || fm.fileExistsAtPath(profile + '/Secure Preferences')) fail('browser_inventory_unavailable');
        continue;
      }
      if (profileInfo.NSFileType !== 'NSFileTypeDirectory') continue;
      var preferenceFiles = [profile + '/Preferences', profile + '/Secure Preferences'];
      for (var f = 0; f < preferenceFiles.length; f++) {
        var file = preferenceFiles[f];
        if (!exists(file)) continue;
        if (attributes(profile).NSFileType !== 'NSFileTypeDirectory') fail('browser_inventory_unavailable');
        var prefs = read(file), extensions = prefs.extensions;
        if (extensions === undefined) continue;
        if (!object(extensions)) fail('browser_inventory_unavailable');
        if (extensions.settings === undefined) continue;
        if (!object(extensions.settings)) fail('browser_inventory_unavailable');
        var entry = extensions.settings[extensionID];
        if (entry === undefined) continue;
        if (!object(entry)) fail('browser_inventory_unavailable');
        found++;
        if (entry.manifest && (!object(entry.manifest) || typeof entry.manifest.version !== 'string')) fail('browser_inventory_unavailable');
        var remembered = entry.manifest && entry.manifest.version;
        if (!passive && remembered && !/^4\.2\.\d{1,3}$/.test(remembered)) fail('legacy_browser_extension');
        if (typeof entry.path !== 'string' || !entry.path || /[\x00-\x1f\x7f]/.test(entry.path)) fail('browser_inventory_unavailable');
        if (entry.path[0] !== '/' && entry.path.split('/').indexOf('..') !== -1) fail('browser_inventory_unavailable');
        var source = normalize(entry.path[0] === '/' ? entry.path : profile + '/Extensions/' + entry.path);
        if (!exists(source) || attributes(source).NSFileType !== 'NSFileTypeDirectory') fail('browser_inventory_unavailable');
        var manifest = read(source + '/manifest.json');
        if (typeof manifest.version !== 'string') fail('browser_inventory_unavailable');
        if (!passive && !/^4\.2\.\d{1,3}$/.test(manifest.version)) fail('legacy_browser_extension');
        if (manifest.key !== expectedKey || (entry.manifest && entry.manifest.key && entry.manifest.key !== expectedKey)) fail('browser_inventory_unavailable');
        if (remembered && remembered !== manifest.version) fail('browser_inventory_unavailable');
        if (passive) {
          // Only this observed legacy family may coexist in another profile; it cannot call the host.
          if (source === expected || /^4\.2\./.test(manifest.version)) fail('browser_reconnect_required');
          if (manifest.version !== '3.5.3' || !Array.isArray(manifest.permissions) || manifest.permissions.some(function(x){return typeof x !== 'string';}) || manifest.permissions.indexOf('nativeMessaging') !== -1 ||
              (manifest.optional_permissions !== undefined && (!Array.isArray(manifest.optional_permissions) || manifest.optional_permissions.length !== 0)) ||
              manifest.externally_connectable !== undefined) fail('legacy_browser_extension');
          continue;
        }
        if (bound && (!Array.isArray(manifest.permissions) || manifest.permissions.indexOf('nativeMessaging') === -1 ||
            !Array.isArray(manifest.host_permissions) || manifest.host_permissions.indexOf('https://www.xiaohongshu.com/*') === -1 || manifest.host_permissions.indexOf('https://m.xiaohongshu.com/*') === -1)) fail('browser_inventory_unavailable');
        paths.push(source); versions.push(manifest.version);
        if (paths.some(function(value) { return value !== paths[0]; }) || versions.some(function(value) { return value !== versions[0]; })) fail('browser_inventory_unavailable');
        if (!expected || source !== expected) fail('browser_reconnect_required');
      }
    }
    return found ? 'compatible_registered' : 'clear';
  }
  function privateMetadata(path) {
    var info = attributes(path), home = attributes(ObjC.unwrap($.NSHomeDirectory()));
    if (info.NSFileOwnerAccountID !== home.NSFileOwnerAccountID || Number(info.NSFilePosixPermissions) !== 384 || Number(info.NSFileSize) > 16384) fail('browser_inventory_unavailable');
    return read(path);
  }
  function referenceHash(path) {
    // Fixed OS SHA tool, metadata files only; no shell, browser APIs or cookie reads.
    var info = attributes(path), home = attributes(ObjC.unwrap($.NSHomeDirectory()));
    if (info.NSFileType !== 'NSFileTypeRegular' || info.NSFileOwnerAccountID !== home.NSFileOwnerAccountID || Number(info.NSFileSize) > 16384) fail('browser_inventory_unavailable');
    var task = $.NSTask.alloc.init, output = $.NSPipe.pipe;
    task.launchPath = '/usr/bin/shasum'; task.arguments = ['-a', '256', path];
    task.standardOutput = output; task.standardError = $.NSFileHandle.fileHandleWithNullDevice;
    task.launch;
    var bytes = output.fileHandleForReading.readDataToEndOfFile; task.waitUntilExit;
    var value = ObjC.unwrap($.NSString.alloc.initWithDataEncoding(bytes, $.NSUTF8StringEncoding));
    if (task.terminationStatus !== 0 || typeof value !== 'string' || !/^[a-f0-9]{64}  /.test(value)) fail('browser_inventory_unavailable');
    return value.substring(0, 64);
  }
  function originalBrowserData(session, sessionID) {
    var link = session + '/browser_data', info = fileInfo(link);
    if (!info || info.NSFileType !== 'NSFileTypeSymbolicLink') return link;
    var markerPath = session + '/browser-profile-reference.json', markerInfo = attributes(markerPath), marker = privateMetadata(markerPath);
    if (Number(markerInfo.NSFileSize) > 4096 || Object.keys(marker).sort().join(',') !== 'binding_sha256,browser_data,identity_sha256,platform,schema,session_id' ||
        marker.schema !== 'crowd-pro-original-browser-profile-v1' || marker.session_id !== sessionID || marker.platform !== 'xhs' ||
        typeof marker.browser_data !== 'string' || marker.browser_data[0] !== '/' || /[\x00-\x1f\x7f]/.test(marker.browser_data) ||
        typeof marker.identity_sha256 !== 'string' || typeof marker.binding_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(marker.identity_sha256) || !/^[a-f0-9]{64}$/.test(marker.binding_sha256)) fail('browser_inventory_unavailable');
    var original = marker.browser_data, parent = original.substring(0, original.lastIndexOf('/')), owner = attributes(ObjC.unwrap($.NSHomeDirectory())).NSFileOwnerAccountID;
    if (normalize(original) !== original || ObjC.unwrap($(original).stringByResolvingSymlinksInPath) !== original ||
        !original.endsWith('/sessions/' + sessionID + '/browser_data') || parent === session ||
        ObjC.unwrap($(link).stringByResolvingSymlinksInPath) !== original || attributes(original).NSFileType !== 'NSFileTypeDirectory' || attributes(original).NSFileOwnerAccountID !== owner || attributes(parent).NSFileOwnerAccountID !== owner || info.NSFileOwnerAccountID !== owner) fail('browser_inventory_unavailable');
    for (var i = 0, names = ['identity.json', 'pro-binding.json'], fields = ['identity_sha256', 'binding_sha256']; i < names.length; i++) {
      if (referenceHash(session + '/' + names[i]) !== marker[fields[i]] || referenceHash(parent + '/' + names[i]) !== marker[fields[i]]) fail('browser_inventory_unavailable');
    }
    return original;
  }
  try {
    if ((args.length !== 2 && args.length !== 4) || !args[0] || args[0][0] !== '/') fail('browser_inventory_unavailable');
    var root = normalize(args[0]), expected = args[1] ? normalize(args[1]) : '';
    if (args.length === 2) return scan(root, expected, false, false);
    if (!expected || !args[2] || args[2][0] !== '/' || !args[3] || args[3][0] !== '/') fail('browser_inventory_unavailable');
    var config = privateMetadata(args[3]), settings = privateMetadata(args[2]);
    if (config.directory !== expected || config.extension_key !== expectedKey ||
        Object.keys(settings).sort().join(',') !== 'max_api_requests,mc_root,purpose,python,root,session_id' ||
        typeof settings.root !== 'string' || settings.root[0] !== '/' || settings.root !== normalize(settings.root) ||
        typeof settings.python !== 'string' || settings.python[0] !== '/' || typeof settings.mc_root !== 'string' || settings.mc_root[0] !== '/' ||
        typeof settings.session_id !== 'string' || !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(settings.session_id) ||
        typeof settings.max_api_requests !== 'number' || Math.floor(settings.max_api_requests) !== settings.max_api_requests || settings.max_api_requests < 1 || settings.max_api_requests > 100 || settings.purpose !== 'noncommercial_research') fail('browser_inventory_unavailable');
    var session = settings.root + '/sessions/' + settings.session_id;
    for (var i = 0, dirs = [settings.root, settings.root + '/sessions', session]; i < dirs.length; i++) {
      if (attributes(dirs[i]).NSFileType !== 'NSFileTypeDirectory') fail('browser_inventory_unavailable');
    }
    var identity = read(session + '/identity.json');
    if (Object.keys(identity).join(',') !== 'platform' || identity.platform !== 'xhs') fail('browser_inventory_unavailable');
    var browserData = originalBrowserData(session, settings.session_id);
    if (attributes(browserData).NSFileType !== 'NSFileTypeDirectory') fail('browser_inventory_unavailable');
    var target = browserData + '/xhs_bridge_profile';
    if (scan(target, expected, false, true) !== 'compatible_registered') fail('browser_inventory_unavailable');
    if (target !== root) scan(root, expected, true, false);
    return 'compatible_registered';
  } catch (error) {
    return ['legacy_browser_extension', 'browser_reconnect_required'].indexOf(error.message) !== -1 ? error.message : 'browser_inventory_unavailable';
  }
}
