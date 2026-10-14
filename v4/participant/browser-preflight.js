/* macOS JXA: read only Chrome registration metadata, never cookies or browser APIs. */
ObjC.import('Foundation');
function run(args) {
  var extensionID = 'licijehcpohikchlnkbpjdjdfkcocndg';
  var expectedKey = '@EXTENSION_KEY@';
  var fm = $.NSFileManager.defaultManager, found = 0;
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
  try {
    if (args.length !== 2 || !args[0] || args[0][0] !== '/') fail('browser_inventory_unavailable');
    var root = normalize(args[0]), expected = args[1] ? normalize(args[1]) : '';
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
        if (remembered && !/^4\.2\.\d{1,3}$/.test(remembered)) fail('legacy_browser_extension');
        if (typeof entry.path !== 'string' || !entry.path || /[\x00-\x1f\x7f]/.test(entry.path)) fail('browser_inventory_unavailable');
        if (entry.path[0] !== '/' && entry.path.split('/').indexOf('..') !== -1) fail('browser_inventory_unavailable');
        var source = normalize(entry.path[0] === '/' ? entry.path : profile + '/Extensions/' + entry.path);
        if (!exists(source) || attributes(source).NSFileType !== 'NSFileTypeDirectory') fail('browser_inventory_unavailable');
        var manifest = read(source + '/manifest.json');
        if (typeof manifest.version !== 'string') fail('browser_inventory_unavailable');
        if (!/^4\.2\.\d{1,3}$/.test(manifest.version)) fail('legacy_browser_extension');
        if (manifest.key !== expectedKey || (entry.manifest && entry.manifest.key && entry.manifest.key !== expectedKey)) fail('browser_inventory_unavailable');
        if (remembered && remembered !== manifest.version) fail('browser_inventory_unavailable');
        paths.push(source); versions.push(manifest.version);
        if (paths.some(function(value) { return value !== paths[0]; }) || versions.some(function(value) { return value !== versions[0]; })) fail('browser_inventory_unavailable');
        if (!expected || source !== expected) fail('browser_reconnect_required');
      }
    }
    return found ? 'compatible_registered' : 'clear';
  } catch (error) {
    return ['legacy_browser_extension', 'browser_reconnect_required'].indexOf(error.message) !== -1 ? error.message : 'browser_inventory_unavailable';
  }
}
