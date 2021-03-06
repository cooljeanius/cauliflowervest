#!/usr/bin/env python
# 
# Copyright 2011 Google Inc. All Rights Reserved.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 
#

"""Core storage related features."""



import logging

from cauliflowervest.client import util


DISKUTIL = '/usr/sbin/diskutil'


class Error(Exception):
  """Base error."""


class CouldNotUnlockError(Error):
  """Could not unlock volume error."""


class CouldNotRevertError(Error):
  """Could not revert volume error."""


class VolumeNotEncryptedError(Error):
  """Volume is not encrypted error."""


class State(object):
  """Fake enum to represent the possible states of core storage."""
  enabled = 'CORE_STORAGE_STATE_ENABLED'
  encrypted = 'CORE_STORAGE_STATE_ENCRYPTED'
  none = 'CORE_STORAGE_STATE_NONE'
  unknown = 'CORE_STORAGE_STATE_UNKNOWN'


def IsBootVolumeEncrypted():
  """Returns True if the boot volume (/) is encrypted, False otherwise."""
  try:
    csinfo_plist = util.GetPlistFromExec(
        (DISKUTIL, 'cs', 'info', '-plist', '/'))
  except util.ExecError:
    return False  # Non-zero return means / volume isn't a CoreStorage volume.

  lvf_uuid = csinfo_plist.get('MemberOfCoreStorageLogicalVolumeFamily')
  if lvf_uuid:
    try:
      lvf_info_plist = util.GetPlistFromExec(
          (DISKUTIL, 'cs', 'info', '-plist', lvf_uuid))
    except util.ExecError:
      return False  # Couldn't get info on Logical Volume Family UUID.
    return lvf_info_plist.get(
        'CoreStorageLogicalVolumeFamilyEncryptionType') == 'AES-XTS'

  return False


def GetRecoveryPartition():
  """Determine the location of the recovery partition on disk 0.

  Returns:
    str, like "/dev/disk0s3" where the recovery partition is, OR
    None, if no recovery partition exists or cannot be detected.
  """
  try:
    disklist_plist = util.GetPlistFromExec((DISKUTIL, 'list', '-plist'))
  except util.ExecError:
    logging.exception('GetRecoveryPartition() failed to get partition list.')
    return

  alldisks = disklist_plist.get('AllDisksAndPartitions', [])
  for disk in alldisks:
    if disk.get('DeviceIdentifier') == 'disk0':
      partitions = disk.get('Partitions', [])
      for partition in partitions:
        if partition.get('VolumeName') == 'Recovery HD':
          return '/dev/%s' % partition['DeviceIdentifier']


def GetStateAndVolumeIds():
  """Determine the state of core storage and the volume IDs (if any).

  In the case that core storage is enabled, it is required that every present
  volume is encrypted, to return "encrypted" status (i.e. the entire drive is
  encrypted, for all present drives).  Otherwise only "enabled" status is
  returned.

  Returns:
    tuple: (State, [list; str encrypted UUIDs], [list; str unencrypted UUIDs])
  Raises:
    Error: there was a problem getting the corestorage list, or family info.
  """
  try:
    cs_plist = util.GetPlistFromExec(
        (DISKUTIL, 'corestorage', 'list', '-plist'))
  except util.ExecError:
    logging.exception('GetStateAndVolumeIds() failed to get corestorage list.')
    raise Error

  state = State.none
  volume_ids = []
  encrypted_volume_ids = []

  groups = cs_plist.get('CoreStorageLogicalVolumeGroups', [])
  if groups:
    state = State.enabled
  for group in groups:
    for family in group.get('CoreStorageLogicalVolumeFamilies', []):
      family_id = family['CoreStorageUUID']
      if not util.UuidIsValid(family_id):
        continue
      try:
        info_plist = util.GetPlistFromExec(
            (DISKUTIL, 'corestorage', 'info', '-plist', family_id))
      except util.ExecError:
        logging.exception(
            'GetStateAndVolumeIds() failed to get corestorage family info: %s',
            family_id)
        raise Error
      enc = info_plist.get('CoreStorageLogicalVolumeFamilyEncryptionType', '')

      for volume in family['CoreStorageLogicalVolumes']:
        volume_id = volume['CoreStorageUUID']
        if enc == 'AES-XTS':
          encrypted_volume_ids.append(volume_id)
        else:
          volume_ids.append(volume_id)
  if encrypted_volume_ids and not volume_ids:
    state = State.encrypted
  return state, encrypted_volume_ids, volume_ids


def GetState():
  """Check if core storage is in place.

  Returns:
    One of the class properties of State.
  """
  state, _, _ = GetStateAndVolumeIds()
  return state


def GetVolumeSize(uuid, readable=True):
  """Return the size of the volume with the given UUID.

  Args:
    uuid: str, ID of the volume in question
    readable: Optional boolean, default true: return a human-readable string
      when true, otherwise int number of bytes.

  Returns:
    str or int, see "readable" arg.
  Raises:
    Error: there was a problem getting volume info.
    ValueError: The UUID is formatted incorrectly.
  """
  if not util.UuidIsValid(uuid):
    raise ValueError('Invalid UUID: ' + uuid)
  try:
    plist = util.GetPlistFromExec(
        (DISKUTIL, 'corestorage', 'info', '-plist', uuid))
  except util.ExecError:
    logging.exception('GetVolumeSize() failed to get volume info: %s', uuid)
    raise Error

  num_bytes = plist['CoreStorageLogicalVolumeSize']
  if readable:
    return '%.2f GiB' % (num_bytes / (1<<30))
  else:
    return num_bytes


def UnlockVolume(uuid, passphrase):
  """Unlock a core storage encrypted volume.

  Args:
    uuid: str, uuid of the volume to unlock.
    passphrase: str, passphrase to unlock the volume.
  Raises:
    CouldNotUnlockError: the volume cannot be unlocked.
    ValueError: The UUID is formatted incorrectly.
  """
  if not util.UuidIsValid(uuid):
    raise ValueError('Invalid UUID: ' + uuid)
  returncode, _, stderr = util.Exec(
      (DISKUTIL, 'corestorage', 'unlockVolume', uuid, '-stdinpassphrase'),
      stdin=passphrase)
  if returncode != 0 and not 'volume is not locked' in stderr:
    raise CouldNotUnlockError(
        'Could not unlock volume (%s).' % returncode)


def RevertVolume(uuid, passphrase):
  """Revert a core storage encrypted volume (to unencrypted state).

  Args:
    uuid: str, uuid of the volume to revert.
    passphrase: str, passphrase to unlock the volume.
  Raises:
    CouldNotRevertError: the volume was unlocked, but cannot be reverted.
    CouldNotUnlockError: the volume cannot be unlocked.
    ValueError: The UUID is formatted incorrectly.
  """
  if not util.UuidIsValid(uuid):
    raise ValueError('Invalid UUID: ' + uuid)
  UnlockVolume(uuid, passphrase)
  returncode, _, _ = util.Exec(
      (DISKUTIL, 'corestorage', 'revert', uuid, '-stdinpassphrase'),
      stdin=passphrase)
  if returncode != 0:
    raise CouldNotRevertError('Could not revert volume (%s).' % returncode)