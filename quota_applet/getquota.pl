#! /usr/bin/perl -w
#
# $Id: getquota.pl,v 1.4 2014/06/26 13:20:08 eva Exp $
#
# fairly simple wrapper round call to Quota::query to return the quota
# (usage/total) for the current user's home directory.

# use Quota;
use Sys::Syslog;

# $sverb must be >= $verb or dlog will go wrong...
my $verb=1;
my $sverb=5;
my $cmd='getquota';

sub dlog {
    my ($level, $format, @fa)=@_;
    if ($level <= $sverb) {
	my $msg=$cmd.': '.sprintf($format, @fa);
	# This will syslog at such a level that it makes it to the
	# central logserver...
	syslog('info|authpriv', $msg);
	if ($level <= $verb) {
	    warn  "$msg\n";
	}
    }
}

while($_=shift){		# tainted $_
    /^-verb/&&do{$verb=(shift)+0;next;};
    /^-sverb/&&do{$sverb=(shift)+0;next;};
    die ("usage: $0 [-verb N] []-sverb N]\n");
}
$_=0;				# untaint $_

my $dir=$ENV{'HOME'};
my $uid=$<;
my $user=$ENV{'LOGNAME'};

dlog(10, "got dir=%s LOGNAME=%s uid=%s <=%d >=%d", $dir, $user, $uid, $<, $>);

# Find the user's actual home directory (OSD)
$home=(getpwnam($user))[7];
if (readlink $home) {$home=readlink $home;}
$nfsrem = qx (df -t nfs $home 2>/dev/null | tail -1);
chomp($nfsrem);
$nfsrem=~s/\s.*//;

# system call to quota command
my $quota_string = qx (quota -u $user | grep -A 1 $nfsrem | grep -v home) ;
chomp $quota_string;

# get the usage and max quota values
my @quota_bits = split(/ +/, $quota_string);
my $use = $quota_bits[1];
my $max = $quota_bits[2];

#print "@quota_bits\n";
#print "$quota_bits[1] $quota_bits[2]\n";

# calculate the gap
my $gap=$max - $use;

# how it was using the Perl:Quota module, now deprecated
# dlog(5, "returning: $qdata[0] $qdata[1] (free=$gap) for $user ($uid)");
# print "$qdata[0] $qdata[1] $gap\n";

print "$use $max $gap\n";

exit 0;
